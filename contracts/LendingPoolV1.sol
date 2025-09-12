// SPDX-License-Identifier: GPL-3.0

pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "./stakingV2.sol";
import "./balanceTransfer.sol";

contract LendingPoolV1 is Ownable, ReentrancyGuard{
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    bytes32 public CONTRACT_COLDKEY = bytes32(0);
    bytes32 public TREASURY_COLDKEY = bytes32(0);
    bytes32 public DEFAULT_DELEGATE_HOTKEY = bytes32(0);
    address public MANAGER = address(0);
    string public constant VERSION = "v1";
    uint256 constant MAX_MINER_BOUND = 64;

    bool public paused = false;
    IStaking public immutable staking;
    ISubtensorBalanceTransfer public immutable balanceTransfer;

    mapping (address => mapping(uint256 => uint256)) public userBalance;
    mapping (uint => uint256) public subnetAlphaBalance;

    mapping (address => bytes32) public minerHotkey;
    mapping (bytes32 => address[]) public minerAddresses;
    mapping (bytes32 => uint8) public minerCount;
    mapping (address => bool) public minerBound;

    event DepositAlpha(
        address indexed sender,
        uint256 netuid,
        uint256 alphaAmount,
        bytes32 delegateHotkey
    );
    event WithdrawAlpha(
        address indexed sender,
        uint256 netuid,
        uint256 alphaAmount,
        bytes32 userColdkey,
        bytes32 delegateHotkey
    );
    event DepositTao(
        address indexed sender,
        uint256 taoAmount
    );
    event WithdrawTao(
        address indexed sender,
        uint256 taoAmount
    );
    event AdminWithdrawAlpha(
        address indexed sender,
        uint256 netuid,
        uint256 alphaAmount,
        bytes32 indexed to
    );
    event AdminWithdrawTao(
        address indexed sender,
        uint256 taoAmount,
        bytes32 indexed to
    );
    event AdminMoveAlpha(
        address indexed sender,
        uint256 netuid,
        uint256 alphaAmount,
        bytes32 originHotkey,
        bytes32 destinationHotkey
    );
    event BindMiner(
        address indexed sender,
        bytes32 hotkey,
        uint8 minerCount
    );

    modifier onlyManager() {
        require(MANAGER == msg.sender, "caller is not the manager");
        _;
    }

    constructor() Ownable(msg.sender) {
        staking = IStaking(ISTAKING_ADDRESS);
        balanceTransfer = ISubtensorBalanceTransfer(ISUBTENSOR_BALANCE_TRANSFER_ADDRESS);
    }

    function setContractColdkey(bytes32 _coldkey) public onlyOwner {
        CONTRACT_COLDKEY = _coldkey;
    }

    function setTreasuryColdkey(bytes32 _coldkey) public onlyOwner {
        TREASURY_COLDKEY = _coldkey;
    }

    function setDelegateHotkey(bytes32 _hotkey) public onlyOwner {
        DEFAULT_DELEGATE_HOTKEY = _hotkey;
    }

    function setManager(address _manager) public onlyOwner {
        MANAGER = _manager;
    }

    function pause(bool _paused) public onlyOwner {
        paused = _paused;
    }

    function verifySignature(
        bytes32 _message,
        bytes memory _signature,
        address _signer
    ) internal pure returns (bool) {
        bytes32 ethSignedMessageHash = _message.toEthSignedMessageHash();
        address recoveredSigner = ethSignedMessageHash.recover(_signature);
        return recoveredSigner == _signer;
    }

    function bindMiner(bytes32 _hotkey, bytes memory _signature) public nonReentrant {
        require(!paused, "contract is paused");
        require(minerCount[_hotkey] < MAX_MINER_BOUND, "hotkey reached max miner bound");
        require(!minerBound[msg.sender], "miner already bounded");

        // Verify signature: check that _hotkey was signed by msg.sender
        require(
            verifySignature(_hotkey, _signature, msg.sender),
            "invalid signature: hotkey must be signed by msg.sender"
        );

        minerHotkey[msg.sender] = _hotkey;
        minerAddresses[_hotkey].push(msg.sender);
        minerCount[_hotkey] += 1;
        minerBound[msg.sender] = true;

        emit BindMiner(msg.sender, _hotkey, minerCount[_hotkey]);
    }

    function depositAlpha(uint256 _netuid, uint256 _amount, bytes32 _delegate_hotkey) public nonReentrant {
        require(!paused, "contract is paused");
        require(minerBound[msg.sender], "miner not bounded");

        bytes memory data = abi.encodeWithSelector(
            IStaking.transferStake.selector,
            CONTRACT_COLDKEY,
            _delegate_hotkey,
            _netuid,
            _netuid,
            _amount
        );
        (bool success, ) = address(staking).delegatecall{gas: gasleft()}(data);
        require(success, "user deposit alpha call failed");

        if (_delegate_hotkey != DEFAULT_DELEGATE_HOTKEY) {
            data = abi.encodeWithSelector(
                IStaking.moveStake.selector,
                _delegate_hotkey,
                DEFAULT_DELEGATE_HOTKEY,
                _netuid,
                _netuid,
                _amount
            );
            (success, ) = address(staking).call{gas: gasleft()}(data);
            require(success, "user deposit, move stake call failed");
        }

        userBalance[msg.sender][_netuid] += _amount;
        subnetAlphaBalance[_netuid] += _amount;

        emit DepositAlpha(msg.sender, _netuid, _amount, _delegate_hotkey);
    }

    function withdrawAlpha(uint256 _netuid, uint256 _amount, bytes32 _user_coldkey) public nonReentrant {
        require(!paused, "contract is paused");
        require(userBalance[msg.sender][_netuid] >= _amount, "user withdraw, insufficient alpha balance");

        userBalance[msg.sender][_netuid] -= _amount;
        subnetAlphaBalance[_netuid] -= _amount;

        bytes memory data = abi.encodeWithSelector(
            IStaking.transferStake.selector,
            _user_coldkey,
            DEFAULT_DELEGATE_HOTKEY,
            _netuid,
            _netuid,
            _amount
        );
        (bool success, ) = address(staking).call{gas: gasleft()}(data);
        require(success, "user withdraw alpha call failed");

        emit WithdrawAlpha(msg.sender, _netuid, _amount, _user_coldkey, DEFAULT_DELEGATE_HOTKEY);
    }

    function depositTao() public  payable nonReentrant {
        require(!paused, "contract is paused");
        uint256 rao = msg.value / 1e9; // Convert EVM TAO to MAINNET RAO
        require(rao > 0, "user deposit, amount must be greater than zero");

        bytes memory data = abi.encodeWithSelector(
            IStaking.addStake.selector,
            DEFAULT_DELEGATE_HOTKEY,
            rao,
            0
        );
        (bool success, ) = address(staking).call{value: rao, gas: gasleft()}(data);
        require(success, "user deposit tao call failed");

        userBalance[msg.sender][0] += rao;
        subnetAlphaBalance[0] += rao;

        emit DepositTao(msg.sender, rao);
    }

    function withdrawTao(uint256 _amount) public payable nonReentrant {
        require(!paused, "contract is paused");
        require(userBalance[msg.sender][0] >= _amount, "user withdraw, insufficient tao balance");

        userBalance[msg.sender][0] -= _amount;
        subnetAlphaBalance[0] -= _amount;

        bytes memory data = abi.encodeWithSelector(
            IStaking.removeStake.selector,
            DEFAULT_DELEGATE_HOTKEY,
            _amount,
            0
        );
        (bool success, ) = address(staking).call{gas: gasleft()}(data);
        require(success, "user withdraw tao call failed");

        payable(msg.sender).transfer(_amount * 1e9); // Convert RAO to EVM TAO

        emit WithdrawTao(msg.sender, _amount);
    }

    function adminMoveAlpha(uint256 _netuid, uint256 _amount, bytes32 _origin_hotkey, bytes32 _destination_hotkey) public onlyManager {
        bytes memory data = abi.encodeWithSelector(
            IStaking.moveStake.selector,
            _origin_hotkey,
            _destination_hotkey,
            _netuid,
            _netuid,
            _amount
        );
        (bool success, ) = address(staking).call{gas: gasleft()}(data);
        require(success, "admin move stake call failed");

        emit AdminMoveAlpha(msg.sender, _netuid, _amount, _origin_hotkey, _destination_hotkey);
    }

    function adminWithdrawAlpha(uint256 _netuid, uint256 _amount) public onlyManager {
        uint256 totalStake = staking.getStake(DEFAULT_DELEGATE_HOTKEY, CONTRACT_COLDKEY, _netuid);
        require(totalStake - subnetAlphaBalance[_netuid] >= _amount, "admin withdrawal, insufficient alpha");

        bytes memory data = abi.encodeWithSelector(
            IStaking.transferStake.selector,
            TREASURY_COLDKEY,
            DEFAULT_DELEGATE_HOTKEY,
            _netuid,
            _netuid,
            _amount
        );
        (bool success, ) = address(staking).call{gas: gasleft()}(data);
        require(success, "admin withdraw alpha call failed");

        emit AdminWithdrawAlpha(msg.sender, _netuid, _amount, TREASURY_COLDKEY);
    }

    function adminWithdrawTao(uint256 _amount) public payable onlyManager {
        bytes memory data = abi.encodeWithSelector(
            ISubtensorBalanceTransfer.transfer.selector,
            TREASURY_COLDKEY
        );
        (bool success, ) = address(balanceTransfer).call{value: _amount, gas: gasleft()}(data);
        require(success, "admin withdraw tao call failed");

        emit AdminWithdrawTao(msg.sender, _amount, TREASURY_COLDKEY);
    }

    function subnetBalance(address _user, uint256 _max_netuid) public view returns (uint256[] memory) {
        uint256[] memory balance = new uint256[](_max_netuid + 1);

        for(uint i = 0; i <= _max_netuid; i++) {
            balance[i] = userBalance[_user][i];
        }
        
        return balance;
    }

    function hotkeyBalance(bytes32 _hotkey, uint256 _max_netuid) public view returns(uint256[][] memory) {
        address[] memory addresses = minerAddresses[_hotkey];
        uint256[][] memory balance = new uint256[][](addresses.length);

        for (uint i = 0; i < addresses.length; i++) {
            balance[i] = subnetBalance(addresses[i], _max_netuid);
        }

        return balance;
    }

    receive() external payable {}
    fallback() external payable {}
}
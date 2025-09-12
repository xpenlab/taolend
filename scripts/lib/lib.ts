import { Wallet, ethers } from "ethers";
import { ss58ToPublicKey } from "./address-utils";
import { IStakingV2_ABI } from "./stakingV2";
import {
    DEFAULT_HOTKEY, ISTAKING_V2_ADDRESS,
    ISubtensorBalanceTransfer_ADDRESS,
    LENDING_POOL_V1_ADDRESS
} from "../../const";
import { LENDING_POOL_V1_ABI } from "./ledingPoolV1";

async function depositAlpha(wallet: Wallet, netUid: number, amountToDeposit: bigint, delegateHotkey: string) {
    try {
        console.log("Starting deposit alpha ...");

        const stakePool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);
        console.log(`Depositing to subnet ${netUid} ${ethers.formatUnits(amountToDeposit, "gwei")} alpha`);
        const tx = await stakePool.depositAlpha(netUid, amountToDeposit, ss58ToPublicKey(delegateHotkey));
        console.log(`Deposit alpha successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

async function withdrawAlpha(wallet: Wallet, netUid: number, amountToDeposit: bigint, userColdkey: string) {
    try {
        console.log("Starting withdraw alpha ...");

        const stakePool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);
        console.log(`Withdraw from subnet ${netUid} ${ethers.formatUnits(amountToDeposit, "gwei")} alpha to coldkey ${userColdkey}`);
        const tx = await stakePool.withdrawAlpha(netUid, amountToDeposit, ss58ToPublicKey(userColdkey));
        console.log(`Withdraw alpha successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

async function depositTao(wallet: Wallet, amountToDeposit: bigint) {
    try {
        console.log("Starting deposit TAO ...");

        const stakePool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);
        console.log(`Depositing to subnet 0 ${ethers.formatUnits(amountToDeposit, 9)} TAO`);
        const tx = await stakePool.depositTao({ value: amountToDeposit });
        console.log(`Deposit TAO successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

async function withdrawTao(wallet: Wallet, amountToWithdraw: bigint) {
    try {
        console.log("Starting withdraw TAO ...");

        const stakePool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);
        console.log(`Withdrawing from subnet 0 ${ethers.formatUnits(amountToWithdraw, 9)} TAO`);
        const tx = await stakePool.withdrawTao(amountToWithdraw);
        console.log(`Withdraw TAO successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

async function getPoolAlphaBalance(wallet: Wallet, netUid: number): Promise<bigint> {
    const stakePool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);
    const balance = await stakePool.userBalance(wallet.address, netUid);
    return balance;
}

async function getWalletAlphaBalance(wallet: Wallet, hotkey: string, coldkey: string, netUid: number) {
    const stakeV2 = new ethers.Contract(
        ISTAKING_V2_ADDRESS,
        IStakingV2_ABI,
        wallet
    );

    try {
        const balance = await stakeV2.getStake(ss58ToPublicKey(hotkey), ss58ToPublicKey(coldkey), netUid);
        return balance;
    } catch (error) {
        console.error("Error fetching alpha balance:", error);
        return ethers.toBigInt(0);
    }
}

async function getTAOBalance(wallet: Wallet): Promise<bigint> {
    const provider = wallet.provider!;
    const tao_balance = await provider.getBalance(wallet.address);
    return tao_balance;
}

async function transferAlpha(
    evm_wallet: Wallet,
    destinationAddressSs58: string,
    destNetUid: number,
    alphaAmount: bigint
) {
    console.log(`Sending subnet ${destNetUid} alpha to ss58 address: ${destinationAddressSs58}`);

    const stakeV2 = new ethers.Contract(
        ISTAKING_V2_ADDRESS,
        IStakingV2_ABI,
        evm_wallet
    );

    const destPublicKey = ss58ToPublicKey(destinationAddressSs58);

    try {
        const tx = await stakeV2.transferStake(destPublicKey, ss58ToPublicKey(DEFAULT_HOTKEY), destNetUid, destNetUid, alphaAmount);
        console.log(`Transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Error transferring balance:", error);
    }
}

async function transferTao(
    evm_wallet: Wallet,
    destinationAddressSs58: string,
    value: bigint
) {
    console.log(`Sending balance to ss58 address: ${destinationAddressSs58}`);

    const ISubtensorBalanceTransfer_ABI = [
        {
            inputs: [
                {
                    internalType: "bytes32",
                    name: "data",
                    type: "bytes32",
                },
            ],
            name: "transfer",
            outputs: [],
            stateMutability: "payable",
            type: "function",
        },
    ];

    const SubtensorBalanceTransfer = new ethers.Contract(
        ISubtensorBalanceTransfer_ADDRESS,
        ISubtensorBalanceTransfer_ABI,
        evm_wallet
    );

    // Get the substrate address public key
    const publicKey = ss58ToPublicKey(destinationAddressSs58);

    try {
        const tx = await SubtensorBalanceTransfer.transfer(publicKey, { value });
        console.log(`Transaction hash: ${tx.hash}`);
    } catch (error) {
        console.error("Error transferring balance:", error);
    }
}

async function addStake(
    evm_wallet: Wallet,
    delegateHotkey: string,
    taoAmount: bigint,
    destNetUid: number
) {
    console.log(`Add stake ${taoAmount} TAO to ${destNetUid} delegate hotkey: ${delegateHotkey}`);

    const stakeV2 = new ethers.Contract(
        ISTAKING_V2_ADDRESS,
        IStakingV2_ABI,
        evm_wallet
    );

    try {
        const tx = await stakeV2.addStake(ss58ToPublicKey(delegateHotkey), taoAmount, destNetUid, {
            value: taoAmount
        });
        console.log(`Transaction hash: ${tx.hash}`);
    } catch (error) {
        console.error("Error transferring balance:", error);
    }
}

async function removeStake(
    evm_wallet: Wallet,
    delegateHotkey: string,
    alphaAmount: bigint,
    destNetUid: number
) {
    console.log(`Remove stake ${alphaAmount} ALPHA from ${destNetUid} delegate hotkey: ${delegateHotkey}`);

    const stakeV2 = new ethers.Contract(
        ISTAKING_V2_ADDRESS,
        IStakingV2_ABI,
        evm_wallet
    );

    try {
        const tx = await stakeV2.removeStake(ss58ToPublicKey(delegateHotkey), alphaAmount, destNetUid);
        console.log(`Transaction hash: ${tx.hash}`);
    } catch (error) {
        console.error("Error transferring balance:", error);
    }
}

async function bindMiner(wallet: Wallet, hotkey: string) {
    try {
        console.log("Starting bind miner with signature verification...");

        const stakePool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);
        
        // Convert hotkey from SS58 to bytes32
        const hotkeyBytes32 = ss58ToPublicKey(hotkey);
        console.log(`Hotkey bytes32: ${hotkeyBytes32}`);
        
        // Generate signature: sign the hotkey with the wallet
        const messageBytes = ethers.getBytes(hotkeyBytes32);
        const signature = await wallet.signMessage(messageBytes);
        
        console.log(`Binding miner to hotkey ${hotkey}`);
        console.log(`Signature: ${signature}`);
        
        // Call bindMiner with hotkey and signature
        const tx = await stakePool.bindMiner(hotkeyBytes32, signature);
        console.log(`Bind miner successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

export { depositAlpha, withdrawAlpha, depositTao, withdrawTao, getPoolAlphaBalance, getWalletAlphaBalance, getTAOBalance, transferAlpha, transferTao, bindMiner, addStake, removeStake };

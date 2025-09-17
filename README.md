<div align="center">

# [Tao Lend](https://taolend.io)

</div>

# A TAO Lending Protocol in Bittensor

**TaoLend** is a decentralized lending protocol for the Bittensor (\$TAO) ecosystem. It allows users to lend TAO with confidence while borrowers secure loans using subnet ALPHA as collateral. By unlocking TAO liquidity and keeping ALPHA staked within subnets, TaoLend improves both capital efficiency and network security.liquidity and keeping ALPHA staked within subnets, TaoLend improves both capital efficiency and network security.

Our vision is to advance the TAO-EVM ecosystem, creating deeper integration between Bittensor and the broader decentralized finance landscape, and ultimately bringing greater value to the entire Bittensor network.

## 🚀 Features

* **Point-to-Point**: Lenders and borrowers interact directly to establish loans.
* **Flexible Interest**: Lenders define interest rates according to market conditions.
* **Permissionless**: Lenders and borrowers complete transactions with the contract without requiring third-party approval.
* **Bittensor & EVM Integration**: Seamlessly interact with TAO subnets and the EVM ecosystem.
* **Incentivized Participation**: Earn rewards for lending and borrowing TAO, increasing TAO liquidity while keeping ALPHA locked across subnets.

---

## 🛠️ Getting Started (Active in Phase 1)

### Prerequisites

* \$TAO and subnet \$ALPHA in a compatible wallet (e.g., Bittensor CLI wallet).
* Familiarity with Bittensor EVM and transferring funds between SS58 and EVM H160 addresses.
* Basic understanding of EVM contracts and Bittensor subnets.

### Installation

Install NodeJS and PM2
```bash
sudo apt install build-essential libssl-dev git
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/master/install.sh | bash
source ~/.bashrc
nvm install v20.13.1
nvm use v20.13.1
npm install -g typescript ts-node pm2
```

Download code and install dependency
```bash
git clone https://github.com/xpenlab/taolend
cd taolend
npm install
pip install -r requirement.txt
```


### Miners (Command-line mode for Phase 1)

1. **Register a miner on a subnet**

   ```bash
   btcli subnet register --netuid 116 --wallet.name <your wallet name> --wallet.hotkey <your wallet hotkey>
   ```

2. **Create an EVM wallet**

   ```bash
   cp env.example .env
   ```

   <span style="color:red">Update the ETH_PRIVATE_KEY value in .env with 32 bytes</span>. This generates an EVM wallet address and maps it to a Subtensor SS58 address.
   **Important**: Keep this private key secure, or you will lose all assets in the wallet. DON'T USE THE DEFAULT KEY !!!
   Note: The mirror SS58 address does not have a private key, so you cannot control it directly.

   ```bash
   npx ts-node script/cli.ts miner balance
   ```

   This will display your EVM wallet address, mirror SS58 address, and balances at any time.

3. **Bind miner to EVM wallet**

   ```bash
   npx ts-node script/cli.ts miner bind --hotkey <your miner hotkey>
   ```

4. **Transfer TAO or ALPHA to the EVM wallet**
   Transfer TAO or ALPHA to the SS58 address using `btcli` or the Subtensor wallet. The same balance will appear in both the EVM wallet address and the SS58 address.
   Subsequent actions will be performed using the EVM address.

   ```bash
   btcli stake move --orig-netuid <netuid> --dest-netuid <netuid> --amount <readable amount> --dest <your mirror SS58 address>
   ```

5. **Deposit TAO/ALPHA to the lending pool**

   ```bash
   npx ts-node script/cli.ts deposit alpha --netuid <alpha netuid> --amount <readable amount> --delegate <the alpha delegated hotkey>
   npx ts-node script/cli.ts deposit tao --amount <readable amount>
   ```

6. **Withdraw TAO/ALPHA from the lending pool**

   ```bash
   npx ts-node script/cli.ts withdraw alpha --netuid <alpha netuid> --amount <readable amount>
   npx ts-node script/cli.ts withdraw tao --amount <readable amount>
   ```

7. **Transfer TAO/ALPHA out of the EVM wallet**
   Since you cannot control the mirror SS58 address, assets should be transferred out of the EVM address using the EVM precompile contract.

   ```bash
   npx ts-node script/cli.ts transfer alpha --netuid <alpha netuid> --amount <readable amount> --dest <destination SS58 coldkey address>
   npx ts-node script/cli.ts transfer tao --amount <readable amount> --dest <destination SS58 coldkey address>
   ```

**GUI mode** is available at [taolend.io](https://taolend.io).

### Validators

  Start validator with auto upgrade
   ```bash
   pm2 start --name sn116-auto-upgrade python3 -- start_validator.py --wallet.name <your wallet1> --wallet.hotkey <your hotkey>
   ```

---

## 💡 Incentives

In Phase 1, Bittensor’s decentralized network rewards developers and users who contribute value.

The miner weight is calculated as:

```
          SUM(miner’s deposit amount * subnet alpha price * subnet coefficient)
weight = ---------------------------------------------------------------------
          SUM(all subnet amounts * subnet alpha price * subnet coefficient)
```

* **Subnet coefficient**: Defined by the subnet owner to incentivize specific subnet deposits.
* **Alpha price**: Determined as the average ALPHA price across the last three blocks.

---

## 🗺️ Roadmap Phases

### Phase 1. 💦 Lending Pool Bootstrap

In the initial phase, a shared lending pool is established to bootstrap liquidity. Both miners and participants are encouraged to contribute by depositing TAO and ALPHA into the smart contract pool.

* **Dual-asset contribution**: Miners can deposit TAO and ALPHA into the contract. In return, they receive rewards, incentivizing early participation and liquidity depth.
* **Flexible withdrawal**: Deposited TAO and ALPHA can be withdrawn at any time without lock-up, offering participants flexibility and reduced risk.
* **Subnet reward conversion**: All TAO and ALPHA rewards generated in the contract are automatically swapped into Subnet 116 ALPHA, aligning incentives with subnet growth and strengthening the Subnet 116 ecosystem.

This phase focuses on **liquidity bootstrapping** and **reward alignment**, laying the foundation for the P2P lending system in Phase 2.

---

### Phase 2. 💦 Point-to-Point Protocol Setup

In this phase, we introduce a **peer-to-peer (P2P) lending protocol**, where users use ALPHA as collateral to borrow TAO directly from lenders. The process is governed by smart contracts, ensuring trustless execution without centralized risk.

#### Lender

* **Deposit TAO to contract wallet**: Lenders deposit TAO into the lending contract wallet to provide liquidity.
* **Select subnet and define interest**: Lenders choose the subnet and set loan interest rates (e.g., annualized 5% or block-based interest).
* **Generate a signed offer with expiry**: Lenders generate signed loan offers including loan amount, interest rate, subnet ID, required ALPHA collateral, and loan duration.

#### Borrower

* **Choose lender**: Borrowers browse on-chain offers and select one that fits their needs.
* **Accept the offer**: Borrowers accept by depositing ALPHA collateral into the contract.
* **Receive TAO**: Once collateral is confirmed, the contract automatically transfers TAO to the borrower.
* **Repay the loan**: Borrowers repay principal plus interest before maturity. After repayment, collateral is released. If default occurs, lenders can claim ALPHA collateral.

#### Loan Cycle

* **Flexible loan cycle**: Borrowers specify a minimum loan duration (e.g., 7–30 days). There is no maximum loan period.
* **Early repayment**: After the minimum duration, borrowers may repay at any time. Interest accrues daily.
* **Lender recall option**: After the minimum loan duration, lenders can issue a repayment request, requiring repayment within a fixed period (e.g., 3 days).
* **Default handling**: If the borrower does not repay within this period, the lender may claim all ALPHA collateral to repay the loan.

---

## 💡 Incentives

**Lender incentives**

* Earn TAO staking rewards without lending.
* Earn additional interest income from loans.
* Maintain TAO liquidity without staking directly in subnets.
* Subnet 116 ALPHA rewards:

  * Depositing TAO provides lower-weight rewards.
  * Lending TAO via P2P yields higher-weight rewards.

**Borrower incentives**

* Gain TAO liquidity without selling ALPHA holdings.
* Use borrowed TAO in DeFi or node operations.
* Subnet 116 ALPHA rewards: borrowing TAO via lending earns higher-weight rewards.

**Network incentives**

* Improve TAO liquidity and overall capital efficiency.
* Ensure ALPHA remains locked in subnets, preserving stability and security.

---

## 🔒 Security

TaoLend places a strong emphasis on protocol and user security. Key security features include:

1. **Audited Smart Contracts**: All core contracts undergo professional security audits to identify and mitigate vulnerabilities before deployment.
2. **Non-custodial Design**: Users retain full control of their assets at all times; the protocol never takes custody of user funds outside of contract logic.
3. **Collateralization & Liquidation**: Loans are always over-collateralized with ALPHA, and automated liquidation mechanisms protect lenders from borrower default.
4. **Permissionless & Transparent**: All transactions and contract logic are fully on-chain and open source, ensuring transparency and verifiability.
5. **Role Separation & Access Control**: Administrative functions are strictly limited and protected by multi-signature or timelock mechanisms to prevent misuse.
6. **Continuous Monitoring**: The protocol is subject to ongoing monitoring and community review to quickly address any emerging threats or vulnerabilities.

---
## 📜 License

TaoLend is MIT licensed. See [LICENSE](LICENSE).


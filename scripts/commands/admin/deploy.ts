import { ethers } from "hardhat";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";

let deployer: HardhatEthersSigner | undefined;

async function main() {
    try {
        console.log("Starting deployment...");

        const network = await ethers.provider.getNetwork();
        console.log(
          `Deploying to network: ${network.name} (chain ID: ${network.chainId})`
        );

        [deployer] = await ethers.getSigners();
        console.log(`Deploying with account: ${deployer.address}`);
        const balance = await ethers.provider.getBalance(deployer.address);
        console.log(`Account balance: ${ethers.formatEther(balance)} TAO`);

        const lendingPool = await deployLendingPool();
        console.log("Contracts deployed and configured successfully! 🌀");

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

async function deployLendingPool() {

    console.log("Deploying LendingPool v1 contract...");
    const factory = await ethers.getContractFactory("LendingPoolV1", deployer);
    const token = await factory.deploy();

    await token.waitForDeployment();
    console.log(`LendingPool deployed to ${token.target}`);

    return token;
}



main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

import { Wallet, ethers } from "ethers";
import { DEFAULT_HOTKEY, ISTAKING_V2_ADDRESS, LENDING_POOL_V1_ADDRESS } from "../../../const";
import { LENDING_POOL_V1_ABI } from "../../lib/ledingPoolV1";
import { config } from "../../../config";
import {
    encodeAddress,
} from "@polkadot/util-crypto";
import { IStakingV2_ABI } from "../../lib/stakingV2";
import { ss58ToPublicKey } from "../../lib/address-utils";

async function main() {
    try {
        const provider = new ethers.JsonRpcProvider(config.rpcUrl);
        const wallet = new Wallet(config.ethPrivateKey, provider);
        const lendingPool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);
        const stakeV2 = new ethers.Contract(ISTAKING_V2_ADDRESS, IStakingV2_ABI, wallet);

        console.log("Contract Address:", LENDING_POOL_V1_ADDRESS);
        let contractColdkey = await lendingPool.CONTRACT_COLDKEY();
        console.log(`Contract Coldkey: ${encodeAddress(contractColdkey, 42)}`);
        let delegateHotkey = await lendingPool.DEFAULT_DELEGATE_HOTKEY();
        console.log(`Delegate  Hotkey: ${encodeAddress(delegateHotkey, 42)}`);
        let treasuryColdkey = await lendingPool.TREASURY_COLDKEY();
        console.log(`Treasury Coldkey: ${encodeAddress(treasuryColdkey, 42)}`);
        let managerAddress = await lendingPool.MANAGER();
        console.log(`Manager  Address: ${managerAddress}`);
        let pauseState = await lendingPool.paused();
        console.log(`Pause State: ${pauseState}`);

        let taoBalance = await provider.getBalance(LENDING_POOL_V1_ADDRESS);
        console.log(`TAO Balance: ${ethers.formatUnits(taoBalance, 18)}`);

        let totalStake = await stakeV2.getTotalColdkeyStake(contractColdkey);
        console.log(`Total Stake: ${ethers.formatUnits(totalStake, 9)}`);
        for (let i = 0; i < 129; i++) {
            let subnetAsset = await lendingPool.subnetAlphaBalance(i);
            let stakeAsset = await stakeV2.getStake(ss58ToPublicKey(DEFAULT_HOTKEY), contractColdkey, i);
            if (subnetAsset > 0n || stakeAsset > 0n) {
                const subnetAssetStr = ethers.formatUnits(subnetAsset, "gwei");
                const stakeAssetStr = ethers.formatUnits(stakeAsset, "gwei");
                const diff = ethers.formatUnits(stakeAsset - subnetAsset, "gwei");
                console.log(
                    `   #${String(i).padStart(4)}: ${subnetAssetStr.padStart(15)} ${stakeAssetStr.padStart(15)} ${diff.padStart(15)}`
                );
            }
        }
    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});


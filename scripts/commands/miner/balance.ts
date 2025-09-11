import { ethers } from "ethers";
import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { DEFAULT_HOTKEY } from "../../../const";
import { getTAOBalance, getPoolAlphaBalance, getWalletAlphaBalance } from "../../lib/lib";
import { config } from "../../../config";
import { convertH160ToSS58 } from "../../lib/address-utils";

type Args = {
};

export const balanceCommand: CommandModule<{}, Args> = {
    command: "balance",
    describe: "Check ALPHA balance on subnet",
    handler: async (argv: ArgumentsCamelCase<Args>) => {
        const provider = new ethers.JsonRpcProvider(config.rpcUrl);
        const wallet = new ethers.Wallet(config.ethPrivateKey, provider!);
        const mirror_ss58 = convertH160ToSS58(wallet.address);

        console.log(`Miner EVM wallet addr: ${wallet.address}`);
        console.log(`Miner EVM mirror ss58: ${mirror_ss58}`);

        console.log(
            `Miner TAO balance: ${ethers.formatEther(
                await getTAOBalance(wallet)
            )} TAO`
        );

        console.log(`Miner ALPHA balance:`);
        for (let i = 0; i <= 128; i++) {
            let walletAlpha = await getWalletAlphaBalance(wallet, DEFAULT_HOTKEY, mirror_ss58, i)
            let poolAlpha = await getPoolAlphaBalance(wallet, i)
            if (walletAlpha === 0n && poolAlpha === 0n) {
                continue;
            }
            const walletAlphaStr = ethers.formatUnits(walletAlpha, "gwei");
            const poolAlphaStr = ethers.formatUnits(poolAlpha, "gwei");

            console.log(
                `   #${String(i).padStart(4)}: ${walletAlphaStr.padStart(15)}  ${poolAlphaStr.padStart(15)}`
            );
        }
    }
};
import { ethers, Wallet } from "ethers";
import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { convertH160ToSS58 } from "../../lib/address-utils";
import { removeStake, getWalletAlphaBalance } from "../../lib/lib";
import { config } from "../../../config";

type Args = {
    amount: string;
    netuid: number;
    delegate: string;
};

export const removeStakeCommand: CommandModule<{}, Args> = {
    command: "remove",
    describe: "Remove ALPHA from subnet",
    builder: (yargs) =>
        yargs
            .option("amount", {
                type: "string",
                describe: "Amount in ALPHA (9 decimals)",
                demandOption: true,
            })
            .option("netuid", {
                type: "number",
                describe: "Network user ID",
                demandOption: true,
            })
            .option("delegate", {
                type: "string",
                describe: "Delegate hotkey SS58 address",
                demandOption: true,
            }),
    handler: async (argv: ArgumentsCamelCase<Args>) => {
        let provider = ethers.getDefaultProvider(config.rpcUrl);

        const amount = ethers.parseUnits(argv.amount, 9);
        const evm_wallet = new Wallet(config.ethPrivateKey, provider);
        const evm_mirror_ss58 = convertH160ToSS58(evm_wallet.address);
        console.log(`EVM wallet addr:  ${evm_wallet.address}`);
        console.log(`EVM mirror ss58:  ${evm_mirror_ss58}`);

        console.log(
            `EVM ALPHA balance: ${ethers.formatEther(
            await getWalletAlphaBalance(evm_wallet, argv.delegate, evm_mirror_ss58, argv.netuid)
        )}`);
        
        await removeStake(
            evm_wallet,
            argv.delegate,
            amount,
            argv.netuid
        );
    }
};

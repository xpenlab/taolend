import { ethers, Wallet } from "ethers";
import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { convertH160ToSS58 } from "../../lib/address-utils";
import { DEFAULT_HOTKEY } from "../../../const";
import { getWalletAlphaBalance, transferAlpha } from "../../lib/lib";
import { config } from "../../../config";

type Args = {
    amount: string;
    netuid: number;
    dest: string;
};

export const transferAlphaCommand: CommandModule<{}, Args>  = {
    command: "alpha",
    describe: "Transfer ALPHA tokens",
    builder: (yargs) =>
        yargs
            .option("amount", {
                type: "string",
                describe: "Amount in ALPHA (9 decimals)",
                demandOption: true,
            })
            .option("netuid", {
                type: "number",
                describe: "Subnet Net UID",
                demandOption: true,
            })
            .option("dest", {
                type: "string",
                describe: "Destination user coldkey SS58 address",
                demandOption: true,
            }),
    handler: async (argv: ArgumentsCamelCase<Args>)  => {
        let provider = ethers.getDefaultProvider(config.rpcUrl);
        const amount = ethers.parseUnits(argv.amount, 9);

        const evm_wallet = new Wallet(config.ethPrivateKey, provider);
        const evm_mirror_ss58 = convertH160ToSS58(evm_wallet.address);
        console.log(`EVM wallet addr:  ${evm_wallet.address}`);
        console.log(`EVM mirror ss58:  ${evm_mirror_ss58}`);

        console.log(
            `EVM Subnet ${argv.netuid} alpha balance: ${ethers.formatUnits(
                await getWalletAlphaBalance(evm_wallet, DEFAULT_HOTKEY, evm_mirror_ss58, argv.netuid),
                "gwei"
            )}`);
        
        await transferAlpha(
            evm_wallet,
            argv.dest,
            argv.netuid,
            amount
        );
    }
};

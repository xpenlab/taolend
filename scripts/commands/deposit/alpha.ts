import { ethers, Wallet } from "ethers";
import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { depositAlpha } from "../../lib/lib";
import { config } from "../../../config";

type Args = {
    amount: string;
    netuid: number;
    delegate: string;
};

export const depositAlphaCommand: CommandModule<{}, Args> = {
    command: "alpha",
    describe: "Deposit ALPHA tokens",
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
            .option("delegate", {
                type: "string",
                describe: "Delegate hotkey SS58 address",
                demandOption: true,
            }),
    handler: async (argv: ArgumentsCamelCase<Args>) => {
        let provider = ethers.getDefaultProvider(config.rpcUrl);
        const amount = ethers.parseUnits(argv.amount, 9);
        const wallet = new Wallet(config.ethPrivateKey, provider);
        await depositAlpha(wallet, argv.netuid, amount, argv.delegate);
    },
};
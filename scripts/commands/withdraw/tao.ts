import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { ethers, Wallet } from "ethers";
import { config } from "../../../config";
import { withdrawTao } from "../../lib/lib";

type Args = {
    amount: string;
};

export const withdrawTaoCommand: CommandModule<{}, Args> = {
    command: "tao",
    describe: "Withdraw TAO tokens",
    builder: (yargs) =>
        yargs
            .option("amount", {
                type: "string",
                describe: "Amount in ALPHA (9 decimals)",
                demandOption: true,
            }),
    handler: async (argv: ArgumentsCamelCase<Args>) => {
        let provider = ethers.getDefaultProvider(config.rpcUrl);
        const amount = ethers.parseUnits(argv.amount, 9);
        const wallet = new Wallet(config.ethPrivateKey, provider);
        await withdrawTao(wallet, amount);
    },
};
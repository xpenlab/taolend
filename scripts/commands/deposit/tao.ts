import { ethers, Wallet } from "ethers";
import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { config } from "../../../config";
import { depositTao } from "../../lib/lib";

type Args = {
    amount: string;
};

export const depositTaoCommand: CommandModule<{}, Args> = {
    command: "tao",
    describe: "Deposit TAO tokens",
    builder: (yargs) =>
        yargs
            .option("amount", {
                type: "string",
                describe: "Amount in TAO (18 decimals)",
                demandOption: true,
            }),
    handler: async (argv: ArgumentsCamelCase<Args>) => {
        let provider = ethers.getDefaultProvider(config.rpcUrl);
        const amount = ethers.parseUnits(argv.amount, 18);
        const wallet = new Wallet(config.ethPrivateKey, provider);
        await depositTao(wallet, amount);
    },
};
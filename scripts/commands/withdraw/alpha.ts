import { ethers, Wallet } from "ethers";
import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { withdrawAlpha } from "../../lib/lib";
import { config } from "../../../config";
import { convertH160ToSS58 } from "../../lib/address-utils";

type Args = {
    amount: string;
    netuid: number;
};

export const withdrawAlphaCommand: CommandModule<{}, Args> = {
    command: "alpha",
    describe: "Withdraw ALPHA tokens",
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
            }),
    handler: async (argv: ArgumentsCamelCase<Args>) => {
        let provider = ethers.getDefaultProvider(config.rpcUrl);
        const amount = ethers.parseUnits(argv.amount, 9);
        const wallet = new Wallet(config.ethPrivateKey, provider);

        const evm_mirror_ss58 = convertH160ToSS58(wallet.address);
        console.log(`EVM wallet addr:  ${wallet.address}`);
        console.log(`EVM mirror ss58:  ${evm_mirror_ss58}`);

        await withdrawAlpha(wallet, argv.netuid, amount, evm_mirror_ss58);
    },
};
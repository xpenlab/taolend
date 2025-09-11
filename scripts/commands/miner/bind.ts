import { ethers, Wallet } from "ethers";
import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { convertH160ToSS58 } from "../../lib/address-utils";
import { config } from "../../../config";
import { bindMiner } from "../../lib/lib";

type Args = {
    hotkey: string;
};

export const bindCommand: CommandModule<{}, Args> = {
    command: "bind",
    describe: "Bind to miner hotkey",
    builder: (yargs) =>
        yargs
            .option("hotkey", {
                type: "string",
                describe: "Miner hotkey SS58 address",
                demandOption: true,
            }),

    handler: async (argv: ArgumentsCamelCase<Args>) => {
        let provider = ethers.getDefaultProvider(config.rpcUrl);

        const evm_wallet = new Wallet(config.ethPrivateKey, provider);
        const evm_mirror_ss58 = convertH160ToSS58(evm_wallet.address);
        console.log(`EVM wallet addr:  ${evm_wallet.address}`);
        console.log(`EVM mirror ss58:  ${evm_mirror_ss58}`);

        await bindMiner(
            evm_wallet,
            argv.hotkey
        );
    }
};

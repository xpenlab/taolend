import { ethers, Wallet } from "ethers";
import type { CommandModule, ArgumentsCamelCase } from "yargs";
import { convertH160ToSS58 } from "../../lib/address-utils";
import { addStake, getTAOBalance } from "../../lib/lib";
import { config } from "../../../config";

type Args = {
    amount: string;
    netuid: number;
    delegate: string;
};

export const addStakeCommand: CommandModule<{}, Args> = {
    command: "add",
    describe: "Stake TAO  to subnet",
    builder: (yargs) =>
        yargs
            .option("amount", {
                type: "string",
                describe: "Amount in TAO (9 decimals)",
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
            `EVM TAO balance: ${ethers.formatEther(
            await getTAOBalance(evm_wallet)
        )}`);
        
        await addStake(
            evm_wallet,
            argv.delegate,
            amount,
            argv.netuid
        );
    }
};

import { ethers } from "ethers";
import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { DEFAULT_HOTKEY } from "../../const";
import { config } from "../../config";
import { getTAOBalance, getPoolAlphaBalance, getWalletAlphaBalance } from "../lib/lib";
import { convertH160ToSS58 } from "../lib/address-utils";

async function main() {

    const argv = await yargs(hideBin(process.argv))
    .option("netuid", {
        type: "number",
        describe: "Subnetwork UID",
        demandOption: true,
    })
    .option("delegate", {
        type: "string",
        describe: "Delegate address (SS58 format)",
        demandOption: false,
        default: DEFAULT_HOTKEY,
    })
    .strict()
    .parse();

    console.log("Using RPC:", config.rpcUrl);


    const provider = new ethers.JsonRpcProvider(config.rpcUrl);
    const wallet = new ethers.Wallet(config.ethPrivateKey, provider!);
    const mirror_ss58 = convertH160ToSS58(wallet.address);

    console.log(`Miner EVM wallet addr: ${wallet.address}`);
    console.log(`Miner EVM mirror ss58: ${mirror_ss58}`); // you must transfer TAO and alpha to this address before proceeding (for gas + deposits + association tx)

    console.log(
        `Miner TAO balance: ${ethers.formatEther(
            await getTAOBalance(wallet)
        )} t`
    );

    let delegate = DEFAULT_HOTKEY
    if (argv.delegate) {
        delegate = argv.delegate;
    }
    console.log(
        `Miner EVM wallet subnet #${argv.netuid} alpha balance: ${ethers.formatUnits(
            await getWalletAlphaBalance(wallet, delegate, mirror_ss58, argv.netuid),
            "gwei"
        )}`
    );

    console.log(
        `Miner EVM   pool subnet #${argv.netuid} alpha balance: ${ethers.formatUnits(
            await getPoolAlphaBalance(wallet, argv.netuid),
            "gwei"
        )}`
    );
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

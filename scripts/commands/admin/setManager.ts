import { Wallet, ethers } from "ethers";
import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { config } from "../../../config";
import { LENDING_POOL_V1_ADDRESS } from "../../../const";
import { LENDING_POOL_V1_ABI } from "../../lib/ledingPoolV1";

async function main() {
    try {
        const argv = await yargs(hideBin(process.argv))
        .option("address", {
            type: "string",
            describe: "Delegate hotkey SS58 address",
            demandOption: true,
        })
        .strict()
        .parse();

        const provider = new ethers.JsonRpcProvider(config.rpcUrl);
        const wallet = new Wallet(config.ethPrivateKey, provider);
        const lendingPool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);

        console.log("Admin set manager address:", argv.address);
        let tx = await lendingPool.setManager(argv.address);
        console.log(`Admin set manager address successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});


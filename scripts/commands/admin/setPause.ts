import { Wallet, ethers } from "ethers";
import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { LENDING_POOL_V1_ADDRESS } from "../../../const";
import { LENDING_POOL_V1_ABI } from "../../lib/ledingPoolV1";
import { config } from "../../../config";

async function main() {
    try {
        const argv = await yargs(hideBin(process.argv))
        .option("status", {
            type: "boolean",
            describe: "Pause the lending pool",
            demandOption: true,
        })
        .strict()
        .parse();

        const provider = new ethers.JsonRpcProvider(config.rpcUrl);
        const wallet = new Wallet(config.ethPrivateKey, provider);
        const lendingPool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);
        
        console.log("Admin set contract to be:", argv.status ? "paused" : "active");
        let tx = await lendingPool.pause(argv.status);
        console.log(`Admin set contract pause state successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});


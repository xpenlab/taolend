import { Wallet, ethers } from "ethers";
import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { config } from "../../../config";
import { LENDING_POOL_V1_ADDRESS } from "../../../const";
import { LENDING_POOL_V1_ABI } from "../../lib/ledingPoolV1";


async function main() {
    try {
        const argv = await yargs(hideBin(process.argv))
        .option("amount", {
            type: "string",
            describe: "Amount of TAO to withdraw",
            demandOption: true,
        })
        .strict()
        .parse();

        const provider = new ethers.JsonRpcProvider(config.rpcUrl);
        const wallet = new Wallet(config.ethPrivateKey, provider);
        const lendingPool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);

        console.log("Admin withdraw TAO:", argv.amount, ethers.parseUnits(argv.amount, 18));
        let tx = await lendingPool.adminWithdrawTao(ethers.parseUnits(argv.amount, 18), {gasLimit: 300000});
        console.log(`Admin withdraw TAO successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});


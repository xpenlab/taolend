import { Wallet, ethers } from "ethers";
import { convertH160ToSS58, ss58ToPublicKey } from "../../lib/address-utils";
import { LENDING_POOL_V1_ADDRESS } from "../../../const";
import { LENDING_POOL_V1_ABI } from "../../lib/ledingPoolV1";
import { config } from "../../../config";

async function main() {
    try {
        const provider = new ethers.JsonRpcProvider(config.rpcUrl);
        const wallet = new Wallet(config.ethPrivateKey, provider);
        const lendingPool = new ethers.Contract(LENDING_POOL_V1_ADDRESS, LENDING_POOL_V1_ABI, wallet);

        const contractColdkey = convertH160ToSS58(LENDING_POOL_V1_ADDRESS);
        console.log("Admin set contract coldkey:", contractColdkey);
        let tx = await lendingPool.setContractColdkey(ss58ToPublicKey(contractColdkey));
        console.log(`Admin set contract coldkey successfully, transaction hash: ${tx.hash}`);

    } catch (error) {
        console.error("Detailed error information:");
        console.error(error);
    }
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});


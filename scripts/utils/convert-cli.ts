
import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { publicKeyToHex, ss58ToPublicKey } from "../lib/address-utils";

async function main() {

    const argv = await yargs(hideBin(process.argv))
        .option("address", {
        type: "string",
        describe: "Ethereum address",
        demandOption: true,
    })
    .strict()
    .parse();

    let pubkey =  ss58ToPublicKey(argv.address)
    console.log("Public key for address", argv.address, "is", publicKeyToHex(pubkey));
}
main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

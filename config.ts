import { BigNumberish } from "ethers";
import dotenv from "dotenv";

dotenv.config();

const netuid: BigNumberish = 0x7e; // SN116

export const config = {
    ethPrivateKey: process.env.ETH_PRIVATE_KEY || "",
    rpcUrl: process.env.RPC_URL || "http://127.0.0.1:9944",
    netuid,
};

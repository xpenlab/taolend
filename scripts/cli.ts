#!/usr/bin/env node

import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { depositCommand } from "./commands/deposit";
import { withdrawCommand } from "./commands/withdraw";
import { transferCommand } from "./commands/transfer";
import { minerCommand } from "./commands/miner";

yargs(hideBin(process.argv))
    .scriptName("tao-cli")
    .command(depositCommand)
    .command(withdrawCommand)
    .command(transferCommand)
    .command(minerCommand)
    .demandCommand(1)
    .strict()
    .help()
    .argv;
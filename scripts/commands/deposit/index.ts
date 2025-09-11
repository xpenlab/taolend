import { CommandModule } from "yargs";
import { depositTaoCommand } from "./tao";
import { depositAlphaCommand } from "./alpha";

export const depositCommand: CommandModule = {
    command: "deposit <subcommand>",
    describe: "Deposit related user actions",
    builder: (yargs) =>
        yargs
            .command(depositTaoCommand)
            .command(depositAlphaCommand) 
            .demandCommand(1, "Please specify a subcommand for deposit"),
    handler: () => {},
};
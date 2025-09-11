import { CommandModule } from "yargs";
import { withdrawTaoCommand } from "./tao";
import { withdrawAlphaCommand } from "./alpha";

export const withdrawCommand: CommandModule = {
    command: "withdraw <subcommand>",
    describe: "Withdraw related user actions",
    builder: (yargs) =>
        yargs
            .command(withdrawTaoCommand)
            .command(withdrawAlphaCommand)
            .demandCommand(1, "Please specify a subcommand for withdraw"),
    handler: () => {},
};
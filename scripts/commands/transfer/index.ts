import { CommandModule } from "yargs";
import { transferTaoCommand } from "./tao";
import { transferAlphaCommand } from "./alpha";

export const transferCommand: CommandModule = {
    command: "transfer <subcommand>",
    describe: "Transfer related user actions",
    builder: (yargs) =>
        yargs
            .command(transferTaoCommand)
            .command(transferAlphaCommand)
            .demandCommand(1, "Please specify a subcommand for transfer"),
    handler: () => {},
};
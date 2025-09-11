import { CommandModule } from "yargs";
import { bindCommand } from "./bind"
import { addStakeCommand } from "./add";
import { removeStakeCommand } from "./remove";
import { balanceCommand } from "./balance";

export const minerCommand: CommandModule = {
    command: "miner <subcommand>",
    describe: "Miner related user actions",
    builder: (yargs) =>
        yargs
            .command(bindCommand)
            .command(addStakeCommand)
            .command(removeStakeCommand)
            .command(balanceCommand)
            .demandCommand(1, "Please specify a subcommand for miner"),
    handler: () => {},
};
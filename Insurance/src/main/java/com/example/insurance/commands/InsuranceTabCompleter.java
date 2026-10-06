package com.example.insurance.commands;

import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class InsuranceTabCompleter implements TabCompleter {

    private static final List<String> MAIN_COMMANDS = Arrays.asList(
            "toggle", "gui", "backup", "buy", "reload", "admin"
    );

    private static final List<String> ADMIN_SUBCOMMANDS = Arrays.asList(
            "permit", "forbid", "level1", "level2", "remove"
    );

    private static final List<String> PERMIT_FORBID_LEVELS = Arrays.asList(
            "level1", "level2", "all"
    );

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        List<String> completions = new ArrayList<>();

        if (args.length == 1) {
            String input = args[0].toLowerCase();
            completions = MAIN_COMMANDS.stream()
                    .filter(cmd -> cmd.startsWith(input))
                    .collect(Collectors.toList());

            if (!sender.hasPermission("insurance.admin")) {
                completions.remove("toggle");
                completions.remove("reload");
                completions.remove("admin");
            }
        } else if (args.length == 2) {
            String firstArg = args[0].toLowerCase();

            if (firstArg.equals("admin") && sender.hasPermission("insurance.admin")) {
                String input = args[1].toLowerCase();
                completions = ADMIN_SUBCOMMANDS.stream()
                        .filter(sub -> sub.startsWith(input))
                        .collect(Collectors.toList());
            }
        } else if (args.length == 3) {
            String firstArg = args[0].toLowerCase();
            String secondArg = args[1].toLowerCase();

            if (firstArg.equals("admin") && sender.hasPermission("insurance.admin")) {
                if (secondArg.equals("permit") || secondArg.equals("forbid")) {
                    String input = args[2].toLowerCase();
                    completions = PERMIT_FORBID_LEVELS.stream()
                            .filter(sub -> sub.startsWith(input))
                            .collect(Collectors.toList());
                }
            }
        }

        return completions;
    }
}
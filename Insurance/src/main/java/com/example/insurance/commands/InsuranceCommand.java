package com.example.insurance.commands;

import com.example.insurance.InsurancePlugin;
import com.example.insurance.gui.BackupGUI;
import com.example.insurance.gui.InsuranceGUI;
import com.example.insurance.gui.InsurancePurchaseGUI;
import com.example.insurance.manager.EconomyManager;
import com.example.insurance.manager.InsuranceManager;
import org.bukkit.ChatColor;
import org.bukkit.NamespacedKey;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

public class InsuranceCommand implements CommandExecutor {

    private final InsurancePlugin plugin;
    private final InsuranceManager insuranceManager;
    private final EconomyManager economyManager;
    private final InsuranceGUI insuranceGUI;
    private final BackupGUI backupGUI;
    private final InsurancePurchaseGUI purchaseGUI;

    public InsuranceCommand(InsurancePlugin plugin) {
        this.plugin = plugin;
        this.insuranceManager = plugin.getInsuranceManager();
        this.economyManager = plugin.getEconomyManager();
        this.insuranceGUI = new InsuranceGUI(plugin);
        this.backupGUI = new BackupGUI(plugin);
        this.purchaseGUI = new InsurancePurchaseGUI(plugin);
    }

    /**
     * 检查物品是否是粘液科技（Slimefun）的灵魂绑定物品
     * @param item 要检查的物品
     * @return 如果是灵魂绑定物品返回 true，否则返回 false
     */
    private boolean isSoulbound(ItemStack item) {
        if (item == null || item.getType().isAir()) {
            return false;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return false;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();

        // 方法1: 检查 slimefun:soulbound 布尔值标记
        try {
            NamespacedKey slimefunSoulboundKey = NamespacedKey.fromString("slimefun:soulbound");
            if (slimefunSoulboundKey != null) {
                Boolean isSoulbound = container.get(slimefunSoulboundKey, PersistentDataType.BOOLEAN);
                if (isSoulbound != null && isSoulbound) {
                    return true;
                }
            }
        } catch (Exception e) {
            // 如果获取 NamespacedKey 失败，继续尝试其他方法
        }

        // 方法2: 检查 slimefun:slimefun_item 字符串值是否包含 BOUND 或 INFINITY 关键字
        // 这可以识别 SOULBOUND_SWORD, BOUND_BACKPACK 等所有绑定物品
        // 以及 INFINITY_CROWN, INFINITY_CHESTPLATE 等无尽套装物品
        try {
            NamespacedKey slimefunItemKey = NamespacedKey.fromString("slimefun:slimefun_item");
            if (slimefunItemKey != null) {
                String slimefunItemId = container.get(slimefunItemKey, PersistentDataType.STRING);
                if (slimefunItemId != null) {
                    // 检查是否是灵魂绑定物品（BOUND 关键字）
                    if (slimefunItemId.contains("BOUND")) {
                        return true;
                    }
                    // 检查是否是无尽套装物品（INFINITY 关键字）
                    if (slimefunItemId.contains("INFINITY")) {
                        return true;
                    }
                }
            }
        } catch (Exception e) {
            // 如果获取 NamespacedKey 失败，继续尝试其他方法
        }

        return false;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            sendHelp(sender);
            return true;
        }

        switch (args[0].toLowerCase()) {
            case "toggle":
                handleToggle(sender);
                break;
            case "gui":
                handleGUI(sender);
                break;
            case "backup":
                handleBackup(sender);
                break;
            case "buy":
                handleBuy(sender);
                break;
            case "reload":
                handleReload(sender);
                break;
            case "admin":
                handleAdmin(sender, args);
                break;
            default:
                sendHelp(sender);
                break;
        }

        return true;
    }

    private void handleToggle(CommandSender sender) {
        String permission = plugin.getConfigManager().getPermission("toggle");
        if (!permission.isEmpty() && !sender.hasPermission(permission)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("no_permission"));
            return;
        }

        boolean newState = !plugin.isPluginEnabled();
        plugin.setPluginEnabled(newState);

        String messageKey = newState ? "plugin_enabled" : "plugin_disabled";
        sender.sendMessage(plugin.getConfigManager().getMessage(messageKey));
    }

    private void handleGUI(CommandSender sender) {
        if (!(sender instanceof Player)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("player_only_command"));
            return;
        }

        String permission = plugin.getConfigManager().getPermission("gui");
        if (!permission.isEmpty() && !sender.hasPermission(permission)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("no_permission"));
            return;
        }

        Player player = (Player) sender;
        insuranceGUI.openInsuranceGUI(player);
    }

    private void handleBackup(CommandSender sender) {
        if (!(sender instanceof Player)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("player_only_command"));
            return;
        }

        String permission = plugin.getConfigManager().getPermission("backup");
        if (!permission.isEmpty() && !sender.hasPermission(permission)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("no_permission"));
            return;
        }

        Player player = (Player) sender;
        backupGUI.openBackupGUI(player);
    }

    private void handleBuy(CommandSender sender) {
        if (!(sender instanceof Player)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("player_only_command"));
            return;
        }

        String permission = plugin.getConfigManager().getPermission("use");
        if (!permission.isEmpty() && !sender.hasPermission(permission)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("no_permission"));
            return;
        }

        Player player = (Player) sender;
        ItemStack item = player.getInventory().getItemInMainHand();
        purchaseGUI.openPurchaseGUI(player, item);
    }

    private void handleReload(CommandSender sender) {
        String permission = plugin.getConfigManager().getPermission("reload");
        if (!permission.isEmpty() && !sender.hasPermission(permission)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("no_permission"));
            return;
        }

        plugin.getConfigManager().reloadConfig();
        sender.sendMessage(ChatColor.GREEN + "配置文件已重新加载！");
    }

    private void handleAdmin(CommandSender sender, String[] args) {
        if (!(sender instanceof Player)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("player_only_command"));
            return;
        }

        Player player = (Player) sender;

        String permission = plugin.getConfigManager().getPermission("admin");
        if (!permission.isEmpty() && !sender.hasPermission(permission)) {
            sender.sendMessage(plugin.getConfigManager().getMessage("no_permission"));
            return;
        }

        if (args.length < 2) {
            sender.sendMessage(ChatColor.RED + "用法: /insurance admin <permit|forbid|level1|level2|remove> [level1|level2|all]");
            return;
        }

        ItemStack item = player.getInventory().getItemInMainHand();
        if (item == null || item.getType().isAir()) {
            sender.sendMessage(ChatColor.RED + "请手持一个物品");
            return;
        }

        // 检查是否是灵魂绑定物品
        if (isSoulbound(item)) {
            sender.sendMessage(ChatColor.RED + "灵魂绑定物品无法设置管理员保险");
            return;
        }

        String action = args[1].toLowerCase();

        // 处理 permit 和 forbid 命令
        if (action.equals("permit") || action.equals("forbid")) {
            if (args.length < 3) {
                sender.sendMessage(ChatColor.RED + "用法: /insurance admin " + action + " <level1|level2|all>");
                return;
            }

            String level = args[2].toLowerCase();
            if (!level.equals("level1") && !level.equals("level2") && !level.equals("all")) {
                sender.sendMessage(ChatColor.RED + "无效的等级。使用 level1、level2 或 all");
                return;
            }

            insuranceManager.setInsurancePermit(item, action, level);

            // 如果是 forbid 命令，清除现有保险
            if (action.equals("forbid")) {
                insuranceManager.removeInsurance(item);
            }

            player.getInventory().setItemInMainHand(item);

            if (action.equals("permit")) {
                if (level.equals("all")) {
                    sender.sendMessage(ChatColor.GREEN + "已允许该物品投保所有等级");
                } else {
                    sender.sendMessage(ChatColor.GREEN + "已允许该物品投保" + level);
                }
            } else {
                if (level.equals("all")) {
                    sender.sendMessage(ChatColor.GREEN + "已禁止该物品投保所有等级，并清除现有保险");
                } else if (level.equals("level1")) {
                    sender.sendMessage(ChatColor.GREEN + "已禁止该物品投保等级1（只允许等级2），并清除现有保险");
                } else if (level.equals("level2")) {
                    sender.sendMessage(ChatColor.GREEN + "已禁止该物品投保等级2（只允许等级1），并清除现有保险");
                }
            }
            return;
        }

        // 处理原有的 level1、level2 和 remove 命令
        switch (action) {
            case "level1":
                insuranceManager.setAdminInsurance(item, true);
                insuranceManager.setInsurance(item, 1, Integer.MAX_VALUE);
                player.getInventory().setItemInMainHand(item);
                sender.sendMessage(plugin.getConfigManager().getMessage("admin_insurance_added"));
                break;
            case "level2":
                insuranceManager.setAdminInsurance(item, true);
                insuranceManager.setInsurance(item, 2, Integer.MAX_VALUE);
                player.getInventory().setItemInMainHand(item);
                sender.sendMessage(plugin.getConfigManager().getMessage("admin_insurance_added"));
                break;
            case "remove":
                insuranceManager.removeInsurance(item);
                player.getInventory().setItemInMainHand(item);
                sender.sendMessage(ChatColor.GREEN + "已清除该物品的所有保险，现在可以重新投保");
                break;
            default:
                sender.sendMessage(ChatColor.RED + "无效的参数。使用 permit、forbid、level1、level2 或 remove");
                return;
        }
    }

    private void sendHelp(CommandSender sender) {
        sender.sendMessage(ChatColor.GOLD + "=== 保险插件命令 ===");
        sender.sendMessage(ChatColor.YELLOW + "/insurance toggle" + ChatColor.WHITE + " - 切换插件功能");
        sender.sendMessage(ChatColor.YELLOW + "/insurance gui" + ChatColor.WHITE + " - 打开保险信息 GUI");
        sender.sendMessage(ChatColor.YELLOW + "/insurance buy" + ChatColor.WHITE + " - 为手持物品购买保险");
        sender.sendMessage(ChatColor.YELLOW + "/insurance backup" + ChatColor.WHITE + " - 打开备份恢复 GUI");
        
        String adminPermission = plugin.getConfigManager().getPermission("admin");
        String reloadPermission = plugin.getConfigManager().getPermission("reload");
        
        boolean canUseAdmin = adminPermission.isEmpty() || sender.hasPermission(adminPermission);
        boolean canUseReload = reloadPermission.isEmpty() || sender.hasPermission(reloadPermission);
        
        if (canUseAdmin || canUseReload) {
            if (canUseReload) {
                sender.sendMessage(ChatColor.YELLOW + "/insurance reload" + ChatColor.WHITE + " - 重新加载配置文件");
            }
            if (canUseAdmin) {
                sender.sendMessage(ChatColor.YELLOW + "/insurance admin <level1|level2|remove>" + ChatColor.WHITE + " - 管理员保险操作");
            }
        }
    }
}
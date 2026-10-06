package com.example.insurance.listeners;

import com.example.insurance.InsurancePlugin;
import com.example.insurance.manager.BackupManager;
import com.example.insurance.manager.InsuranceManager;
import com.palmergames.bukkit.towny.TownyAPI;
import com.palmergames.bukkit.towny.TownySettings;
import com.palmergames.bukkit.towny.object.Resident;
import com.palmergames.bukkit.towny.object.Town;
import com.palmergames.bukkit.towny.object.TownBlock;
import com.palmergames.bukkit.towny.object.TownBlockType;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class DeathListener implements Listener {

    private final InsurancePlugin plugin;
    private final InsuranceManager insuranceManager;
    private final BackupManager backupManager;
    private final NamespacedKey SOULBOUND_KEY;

    public DeathListener(InsurancePlugin plugin) {
        this.plugin = plugin;
        this.insuranceManager = plugin.getInsuranceManager();
        this.backupManager = plugin.getBackupManager();
        this.SOULBOUND_KEY = new NamespacedKey(plugin, "soulbound");
    }

    /**
     * 检查玩家死亡位置是否在城镇区块，并根据 Towny 配置判断是否应该跳过保险机制
     * @param player 死亡的玩家
     * @return 如果 Towny 配置保留物品且玩家在城镇区块死亡，返回 true（跳过保险），否则返回 false
     */
    private boolean shouldSkipInsuranceForTowny(Player player) {
        // 检查 Towny 插件是否已启用
        if (plugin.getServer().getPluginManager().getPlugin("Towny") == null) {
            return false;
        }

        try {
            Location deathLocation = player.getLocation();
            TownBlock townBlock = TownyAPI.getInstance().getTownBlock(deathLocation);

            // 如果不在城镇区块中，返回 false（不跳过保险）
            if (townBlock == null) {
                return false;
            }

            Resident resident = TownyAPI.getInstance().getResident(player);
            if (resident == null) {
                return false;
            }

            Town playerTown = resident.getTown();
            Town deathTown = townBlock.getTownOrNull();

            // 获取 Towny 配置
            boolean keepInventoryInTowns = getTownyConfigBoolean("global_town_settings.keep_inventory_on_death_in_town", true);
            boolean keepInventoryInOwnTown = getTownyConfigBoolean("global_town_settings.keep_inventory_on_death_in_own_town", true);
            boolean keepInventoryInAlliedTowns = getTownyConfigBoolean("global_town_settings.keep_inventory_on_death_in_allied_town", true);
            boolean keepInventoryInArena = getTownyConfigBoolean("global_town_settings.keep_inventory_on_death_in_arena", true);

            // 检查是否是竞技场区块
            if (townBlock.getType() == TownBlockType.ARENA) {
                // 如果 Towny 配置在竞技场中保留物品，跳过保险
                if (keepInventoryInArena) {
                    return true;
                }
            }

            // 检查是否在自己的城镇中死亡
            if (playerTown != null && playerTown.equals(deathTown)) {
                // 如果 Towny 配置在自己城镇中保留物品，跳过保险
                if (keepInventoryInOwnTown) {
                    return true;
                }
            }

            // 检查是否在盟友城镇中死亡
            if (playerTown != null && deathTown != null && !playerTown.equals(deathTown)) {
                if (playerTown.hasAlly(deathTown)) {
                    // 如果 Towny 配置在盟友城镇中保留物品，跳过保险
                    if (keepInventoryInAlliedTowns) {
                        return true;
                    }
                }
            }

            // 检查是否在任何城镇中死亡（包括敌对城镇）
            if (keepInventoryInTowns) {
                return true;
            }

        } catch (Exception e) {
            plugin.getLogger().warning("Error checking Towny status: " + e.getMessage());
        }

        return false;
    }

    /**
     * 从 Towny 配置文件中获取布尔值配置
     * @param configPath 配置路径
     * @param defaultValue 默认值
     * @return 配置值，如果获取失败则返回默认值
     */
    private boolean getTownyConfigBoolean(String configPath, boolean defaultValue) {
        try {
            java.io.File pluginsFolder = plugin.getDataFolder().getParentFile();
            java.io.File townyConfigFile = new java.io.File(pluginsFolder, "Towny/settings/config.yml");
            if (!townyConfigFile.exists()) {
                return defaultValue;
            }

            org.bukkit.configuration.file.YamlConfiguration config = org.bukkit.configuration.file.YamlConfiguration.loadConfiguration(townyConfigFile);
            String[] pathParts = configPath.split("\\.");

            Object value = config;
            for (String part : pathParts) {
                if (value instanceof org.bukkit.configuration.ConfigurationSection) {
                    value = ((org.bukkit.configuration.ConfigurationSection) value).get(part);
                } else {
                    return defaultValue;
                }
                if (value == null) {
                    return defaultValue;
                }
            }

            if (value instanceof String) {
                String strValue = (String) value;
                // 处理 YAML 布尔值字符串（如 'true', 'false'）
                return Boolean.parseBoolean(strValue);
            } else if (value instanceof Boolean) {
                return (Boolean) value;
            }

            return defaultValue;
        } catch (Exception e) {
            plugin.getLogger().warning("Error reading Towny config: " + e.getMessage());
            return defaultValue;
        }
    }

    /**
     * 检查物品是否是粘液科技（Slimefun）的灵魂绑定物品或无尽套装
     * @param item 要检查的物品
     * @return 如果是灵魂绑定物品或无尽套装返回 true，否则返回 false
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
        // 适用于被灵魂绑定符文附魔的原版物品
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

    @EventHandler
    public void onPlayerDeath(PlayerDeathEvent event) {
        if (!plugin.isPluginEnabled()) {
            return;
        }

        Player player = event.getEntity();
        UUID playerUUID = player.getUniqueId();

        // 检查是否应该因为 Towny 配置而跳过保险机制
        if (shouldSkipInsuranceForTowny(player)) {
            plugin.getLogger().info("Player " + player.getName() + " died in town with Towny inventory protection, skipping insurance.");
            return;
        }

        List<ItemStack> itemsToDrop = new ArrayList<>();
        List<ItemStack> itemsToBackup = new ArrayList<>();

        ItemStack[] inventoryContents = player.getInventory().getContents();

        for (int i = 0; i < inventoryContents.length; i++) {
            ItemStack item = inventoryContents[i];
            if (item == null || item.getType().isAir()) {
                continue;
            }

            // 检查是否是灵魂绑定物品
            if (isSoulbound(item)) {
                // 灵魂绑定物品由粘液科技插件处理，保险插件不处理
                continue;
            }

            // 检查是否可以被备份
            if (!insuranceManager.canBeBackedUp(item)) {
                // 如果不允许备份，物品丢失不被记录
                player.getInventory().setItem(i, null);
                continue;
            }

            int insuranceLevel = insuranceManager.getInsuranceLevel(item);

            // 检查投保许可
            if (!insuranceManager.isInsurancePermitted(item, insuranceLevel)) {
                // 如果不允许投保当前等级，物品丢失不被记录
                player.getInventory().setItem(i, null);
                continue;
            }

            if (insuranceLevel == 0) {
                itemsToBackup.add(item);
                player.getInventory().setItem(i, null);
            } else if (insuranceLevel == 1) {
                ItemStack decreasedItem = insuranceManager.decreaseInsuranceTimes(item);
                int newLevel = insuranceManager.getInsuranceLevel(decreasedItem);

                if (newLevel == 0 && insuranceLevel > 0) {
                    insuranceManager.sendInsuranceExpiredMessage(player, item);
                }

                itemsToDrop.add(decreasedItem);
                player.getInventory().setItem(i, null);
            } else if (insuranceLevel == 2) {
                ItemStack decreasedItem = insuranceManager.decreaseInsuranceTimes(item);
                int newLevel = insuranceManager.getInsuranceLevel(decreasedItem);

                if (newLevel == 0 && insuranceLevel > 0) {
                    insuranceManager.sendInsuranceExpiredMessage(player, item);
                }

                player.getInventory().setItem(i, decreasedItem);
            }
        }

        event.setKeepInventory(true);
        event.getDrops().clear();
        event.getDrops().addAll(itemsToDrop);

        if (!itemsToBackup.isEmpty()) {
            backupManager.saveBackup(playerUUID, itemsToBackup);
        }

        player.sendMessage(org.bukkit.ChatColor.YELLOW + "你已死亡，未被保险的物品现已丢失。使用ins backup取回你需要拿回的物品。未取回的物品将在下次死亡时彻底丢失。");
    }
}
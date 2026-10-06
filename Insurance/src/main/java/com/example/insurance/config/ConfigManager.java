package com.example.insurance.config;

import com.example.insurance.InsurancePlugin;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

import java.util.HashMap;
import java.util.Map;

public class ConfigManager {

    private final InsurancePlugin plugin;
    private FileConfiguration config;
    private final Map<String, Double> valuableItems;

    public ConfigManager(InsurancePlugin plugin) {
        this.plugin = plugin;
        this.config = plugin.getConfig();
        this.valuableItems = new HashMap<>();

        loadValuableItems();
    }

    private void loadValuableItems() {
        ConfigurationSection section = config.getConfigurationSection("valuable_items");
        if (section != null) {
            for (String key : section.getKeys(false)) {
                valuableItems.put(key, section.getDouble(key));
            }
        }
    }

    public int getMaxInsuranceTimes() {
        return config.getInt("max_insurance_times", 10);
    }

    public double getCommonItemPrice() {
        return config.getDouble("common_item_price", 50.0);
    }

    public double getEnchantmentCostMultiplier() {
        return config.getDouble("enchantment_cost_multiplier", 0.10);
    }

    public double getLevel1CostPercentage() {
        return config.getDouble("level_1_cost_percentage", 0.20);
    }

    public double getLevel2CostPercentage() {
        return config.getDouble("level_2_cost_percentage", 1.0);
    }

    public double getUpgradeCostPercentage() {
        return config.getDouble("upgrade_cost_percentage", 0.80);
    }

    public double getBackupRecoveryCostPercentage() {
        return config.getDouble("backup_recovery_cost_percentage", 10.0);
    }

    public double getItemPrice(Material material) {
        return valuableItems.getOrDefault(material.toString(), getCommonItemPrice());
    }

    public String getMessage(String key, Object... args) {
        String message = config.getString("messages." + key, key);
        if (args.length > 0) {
            return String.format(message, args);
        }
        return message;
    }

    public void reloadConfig() {
        plugin.reloadConfig();
        this.config = plugin.getConfig();
        valuableItems.clear();
        loadValuableItems();
    }

    public String getPermission(String permissionType) {
        return config.getString("permissions." + permissionType, "");
    }
}
package com.example.insurance.manager;

import com.example.insurance.InsurancePlugin;
import net.milkbowl.vault.economy.Economy;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

public class EconomyManager {

    private final InsurancePlugin plugin;
    private final Economy economy;

    public EconomyManager(InsurancePlugin plugin, Economy economy) {
        this.plugin = plugin;
        this.economy = economy;
    }

    public boolean hasEnoughMoney(Player player, double amount) {
        if (economy == null) {
            return true;
        }
        return economy.has(player, amount);
    }

    public boolean withdrawMoney(Player player, double amount) {
        if (economy == null) {
            return true;
        }
        return economy.withdrawPlayer(player, amount).transactionSuccess();
    }

    public double calculateBasePrice(ItemStack item) {
        Material material = item.getType();
        return plugin.getConfigManager().getItemPrice(material);
    }

    public double calculateEnchantmentMultiplier(ItemStack item) {
        ItemMeta meta = item.getItemMeta();
        if (meta == null || !meta.hasEnchants()) {
            return 1.0;
        }

        int enchantmentCount = meta.getEnchants().size();
        double multiplier = 1.0 + (enchantmentCount * plugin.getConfigManager().getEnchantmentCostMultiplier());
        return multiplier;
    }

    public double calculateInsurancePrice(ItemStack item, int level, int times) {
        double basePrice = calculateBasePrice(item);
        double enchantmentMultiplier = calculateEnchantmentMultiplier(item);
        double totalPrice = basePrice * enchantmentMultiplier;

        double costPercentage;
        if (level == 1) {
            costPercentage = plugin.getConfigManager().getLevel1CostPercentage();
        } else if (level == 2) {
            costPercentage = plugin.getConfigManager().getLevel2CostPercentage();
        } else {
            return 0.0;
        }

        return totalPrice * costPercentage * times;
    }

    public double calculateUpgradePrice(ItemStack item, int remainingTimes) {
        double basePrice = calculateBasePrice(item);
        double enchantmentMultiplier = calculateEnchantmentMultiplier(item);
        double totalPrice = basePrice * enchantmentMultiplier;
        double upgradePercentage = plugin.getConfigManager().getUpgradeCostPercentage();

        return totalPrice * upgradePercentage * remainingTimes;
    }

    public double calculateRecoveryPrice(ItemStack item) {
        double basePrice = calculateBasePrice(item);
        double enchantmentMultiplier = calculateEnchantmentMultiplier(item);
        double totalPrice = basePrice * enchantmentMultiplier;
        double recoveryPercentage = plugin.getConfigManager().getBackupRecoveryCostPercentage();

        return totalPrice * recoveryPercentage;
    }

    public String formatMoney(double amount) {
        if (economy == null) {
            return String.format("%.2f", amount);
        }
        return economy.format(amount);
    }
}
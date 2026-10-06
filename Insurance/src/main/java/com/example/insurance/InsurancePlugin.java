package com.example.insurance;

import com.example.insurance.commands.InsuranceCommand;
import com.example.insurance.commands.InsuranceTabCompleter;
import com.example.insurance.config.ConfigManager;
import com.example.insurance.listeners.DeathListener;
import com.example.insurance.manager.BackupManager;
import com.example.insurance.manager.EconomyManager;
import com.example.insurance.manager.InsuranceManager;
import net.milkbowl.vault.economy.Economy;
import org.bukkit.Bukkit;
import org.bukkit.plugin.RegisteredServiceProvider;
import org.bukkit.plugin.java.JavaPlugin;

public class InsurancePlugin extends JavaPlugin {

    private static InsurancePlugin instance;
    private Economy economy;
    private ConfigManager configManager;
    private InsuranceManager insuranceManager;
    private BackupManager backupManager;
    private EconomyManager economyManager;

    private boolean pluginEnabled;

    @Override
    public void onEnable() {
        instance = this;

        saveDefaultConfig();
        configManager = new ConfigManager(this);

        if (!setupEconomy()) {
            getLogger().warning("Vault not found! Economy features will be disabled.");
        }

        economyManager = new EconomyManager(this, economy);
        insuranceManager = new InsuranceManager(this);
        backupManager = new BackupManager(this);

        Bukkit.getPluginManager().registerEvents(new DeathListener(this), this);

        getCommand("insurance").setExecutor(new InsuranceCommand(this));
        getCommand("ins").setExecutor(new InsuranceCommand(this));
        getCommand("insurance").setTabCompleter(new InsuranceTabCompleter());
        getCommand("ins").setTabCompleter(new InsuranceTabCompleter());

        boolean keepInventory = Bukkit.getWorlds().get(0).getGameRuleValue(org.bukkit.GameRule.KEEP_INVENTORY);
        pluginEnabled = !keepInventory;

        getLogger().info("Insurance Plugin has been enabled!");
        getLogger().info("Plugin feature is " + (pluginEnabled ? "enabled" : "disabled"));
    }

    @Override
    public void onDisable() {
        getLogger().info("Insurance Plugin has been disabled!");
    }

    private boolean setupEconomy() {
        if (getServer().getPluginManager().getPlugin("Vault") == null) {
            return false;
        }
        RegisteredServiceProvider<Economy> rsp = getServer().getServicesManager().getRegistration(Economy.class);
        if (rsp == null) {
            return false;
        }
        economy = rsp.getProvider();
        return economy != null;
    }

    public static InsurancePlugin getInstance() {
        return instance;
    }

    public Economy getEconomy() {
        return economy;
    }

    public ConfigManager getConfigManager() {
        return configManager;
    }

    public InsuranceManager getInsuranceManager() {
        return insuranceManager;
    }

    public BackupManager getBackupManager() {
        return backupManager;
    }

    public EconomyManager getEconomyManager() {
        return economyManager;
    }

    public boolean isPluginEnabled() {
        return pluginEnabled;
    }

    public void setPluginEnabled(boolean enabled) {
        this.pluginEnabled = enabled;
    }
}
package com.example.insurance.manager;

import com.example.insurance.InsurancePlugin;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import org.bukkit.enchantments.Enchantment;

import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public class BackupManager {

    private final InsurancePlugin plugin;
    private final File backupFolder;
    private final Gson gson;

    public BackupManager(InsurancePlugin plugin) {
        this.plugin = plugin;
        this.backupFolder = new File(plugin.getDataFolder(), "backups");

        if (!backupFolder.exists()) {
            backupFolder.mkdirs();
        }

        this.gson = new GsonBuilder().setPrettyPrinting().create();
    }

    public void saveBackup(UUID playerUUID, List<org.bukkit.inventory.ItemStack> items) {
        File backupFile = new File(backupFolder, playerUUID.toString() + ".json");

        List<ItemStackData> itemDataList = new ArrayList<>();
        for (org.bukkit.inventory.ItemStack item : items) {
            itemDataList.add(new ItemStackData(item));
        }

        try (FileWriter writer = new FileWriter(backupFile)) {
            gson.toJson(itemDataList, writer);
        } catch (IOException e) {
            plugin.getLogger().severe("Failed to save backup for player " + playerUUID + ": " + e.getMessage());
        }
    }

    public List<org.bukkit.inventory.ItemStack> loadBackup(UUID playerUUID) {
        File backupFile = new File(backupFolder, playerUUID.toString() + ".json");

        if (!backupFile.exists()) {
            return new ArrayList<>();
        }

        try (FileReader reader = new FileReader(backupFile)) {
            Type listType = new TypeToken<List<ItemStackData>>() {}.getType();
            List<ItemStackData> itemDataList = gson.fromJson(reader, listType);

            List<org.bukkit.inventory.ItemStack> items = new ArrayList<>();
            for (ItemStackData data : itemDataList) {
                items.add(data.toItemStack());
            }

            return items;
        } catch (IOException e) {
            plugin.getLogger().severe("Failed to load backup for player " + playerUUID + ": " + e.getMessage());
            return new ArrayList<>();
        }
    }

    public boolean hasBackup(UUID playerUUID) {
        File backupFile = new File(backupFolder, playerUUID.toString() + ".json");
        return backupFile.exists();
    }

    public void deleteBackup(UUID playerUUID) {
        File backupFile = new File(backupFolder, playerUUID.toString() + ".json");
        if (backupFile.exists()) {
            backupFile.delete();
        }
    }

    private static class ItemStackData {
        private final Map<String, Object> serializedItem;

        public ItemStackData(org.bukkit.inventory.ItemStack item) {
            this.serializedItem = item.serialize();
        }

        public org.bukkit.inventory.ItemStack toItemStack() {
            return org.bukkit.inventory.ItemStack.deserialize(serializedItem);
        }
    }
}
package com.example.insurance.gui;

import com.example.insurance.InsurancePlugin;
import com.example.insurance.manager.InsuranceManager;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class InsuranceGUI implements Listener {

    private final InsurancePlugin plugin;
    private final InsuranceManager insuranceManager;
    private final Map<Player, Integer> selectedSlots;
    private final Map<Player, Integer> pendingCancelSlots;

    public InsuranceGUI(InsurancePlugin plugin) {
        this.plugin = plugin;
        this.insuranceManager = plugin.getInsuranceManager();
        this.selectedSlots = new HashMap<>();
        this.pendingCancelSlots = new HashMap<>();

        plugin.getServer().getPluginManager().registerEvents(this, plugin);
    }

    public void openInsuranceGUI(Player player) {
        Inventory inventory = Bukkit.createInventory(null, 54, ChatColor.GOLD + "物品保险信息");

        ItemStack[] playerInventory = player.getInventory().getContents();

        for (int i = 0; i < playerInventory.length; i++) {
            ItemStack item = playerInventory[i];
            if (item == null || item.getType().isAir()) {
                continue;
            }

            ItemStack displayItem = item.clone();
            ItemMeta meta = displayItem.getItemMeta();

            if (meta != null) {
                List<String> lore = meta.getLore() != null ? new ArrayList<>(meta.getLore()) : new ArrayList<>();

                int level = insuranceManager.getInsuranceLevel(item);
                int times = insuranceManager.getInsuranceTimes(item);
                boolean adminInsurance = insuranceManager.hasAdminInsurance(item);
                String permit = insuranceManager.getInsurancePermit(item);

                lore.add("");
                lore.add(ChatColor.YELLOW + "=== 保险信息 ===");
                lore.add(ChatColor.WHITE + "保险等级: " + getLevelText(level));
                lore.add(ChatColor.WHITE + "保险次数: " + (adminInsurance ? "无限" : times));
                if (adminInsurance) {
                    lore.add(ChatColor.RED + "管理员保险");
                }

                // 显示投保许可信息
                if (!permit.equals("none")) {
                    lore.add("");
                    lore.add(ChatColor.YELLOW + "=== 投保许可 ===");

                    if (permit.equals("forbidden")) {
                        lore.add(ChatColor.RED + "禁止投保所有等级");
                    } else if (permit.equals("level1")) {
                        lore.add(ChatColor.GREEN + "允许投保等级1");
                        lore.add(ChatColor.RED + "禁止投保等级2");
                    } else if (permit.equals("level2")) {
                        lore.add(ChatColor.RED + "禁止投保等级1");
                        lore.add(ChatColor.GREEN + "允许投保等级2");
                    } else if (permit.equals("all")) {
                        lore.add(ChatColor.GREEN + "允许投保所有等级");
                    }
                }

                lore.add("");
                lore.add(ChatColor.GRAY + "点击此物品查看操作");

                meta.setLore(lore);
                displayItem.setItemMeta(meta);
            }

            inventory.setItem(i, displayItem);
        }

        ItemStack closeItem = new ItemStack(Material.BARRIER);
        ItemMeta closeMeta = closeItem.getItemMeta();
        if (closeMeta != null) {
            closeMeta.setDisplayName(ChatColor.RED + "关闭");
            closeItem.setItemMeta(closeMeta);
        }
        inventory.setItem(45, closeItem);

        player.openInventory(inventory);
    }

    private String getLevelText(int level) {
        switch (level) {
            case 0:
                return ChatColor.RED + "无保险";
            case 1:
                return ChatColor.GREEN + "等级 1 (掉落)";
            case 2:
                return ChatColor.BLUE + "等级 2 (保留)";
            default:
                return ChatColor.GRAY + "未知";
        }
    }

    @EventHandler
    public void onInventoryClick(InventoryClickEvent event) {
        if (!(event.getWhoClicked() instanceof Player)) {
            return;
        }

        Player player = (Player) event.getWhoClicked();
        String title = event.getView().getTitle();

        if (title.equals(ChatColor.GOLD + "物品保险信息")) {
            handleMainGUIClick(event, player);
        } else if (title.equals(ChatColor.GOLD + "物品操作")) {
            handleActionGUIClick(event, player);
        } else if (title.equals(ChatColor.RED + "确认取消保险")) {
            handleConfirmGUIClick(event, player);
        }
    }

    private void handleMainGUIClick(InventoryClickEvent event, Player player) {
        event.setCancelled(true);

        int slot = event.getSlot();

        if (slot == 45) {
            player.closeInventory();
            return;
        }

        if (slot < 0 || slot >= 45) {
            return;
        }

        ItemStack clickedItem = event.getCurrentItem();
        if (clickedItem == null || clickedItem.getType().isAir()) {
            return;
        }

        ItemStack playerItem = player.getInventory().getItem(slot);
        if (playerItem == null || playerItem.getType().isAir()) {
            return;
        }

        int level = insuranceManager.getInsuranceLevel(playerItem);
        if (level == 0) {
            player.sendMessage(ChatColor.RED + "该物品没有保险");
            return;
        }

        boolean adminInsurance = insuranceManager.hasAdminInsurance(playerItem);
        if (adminInsurance) {
            player.sendMessage(ChatColor.RED + "管理员保险无法取消");
            return;
        }

        selectedSlots.put(player, slot);
        openActionGUI(player, playerItem, slot);
    }

    private void handleActionGUIClick(InventoryClickEvent event, Player player) {
        event.setCancelled(true);

        int slot = event.getSlot();
        Integer originalSlot = selectedSlots.get(player);

        if (originalSlot == null) {
            player.closeInventory();
            return;
        }

        ItemStack playerItem = player.getInventory().getItem(originalSlot);
        if (playerItem == null) {
            player.sendMessage(ChatColor.RED + "物品不存在");
            player.closeInventory();
            return;
        }

        switch (slot) {
            case 11:
                pendingCancelSlots.put(player, originalSlot);
                openConfirmGUI(player);
                break;
            case 15:
                player.closeInventory();
                break;
        }
    }

    private void handleConfirmGUIClick(InventoryClickEvent event, Player player) {
        event.setCancelled(true);

        int slot = event.getSlot();
        Integer originalSlot = pendingCancelSlots.get(player);

        if (originalSlot == null) {
            player.closeInventory();
            return;
        }

        switch (slot) {
            case 11:
                ItemStack playerItem = player.getInventory().getItem(originalSlot);
                if (playerItem != null) {
                    insuranceManager.removeInsurance(playerItem);
                    player.getInventory().setItem(originalSlot, playerItem);
                    player.sendMessage(ChatColor.RED + "保险已取消！保费不会返还");
                }
                pendingCancelSlots.remove(player);
                selectedSlots.remove(player);
                player.closeInventory();
                break;
            case 15:
                pendingCancelSlots.remove(player);
                openActionGUI(player, player.getInventory().getItem(originalSlot), originalSlot);
                break;
        }
    }

    private void openActionGUI(Player player, ItemStack item, int slot) {
        Inventory inventory = Bukkit.createInventory(null, 27, ChatColor.GOLD + "物品操作");

        ItemStack lavaBucket = new ItemStack(Material.LAVA_BUCKET);
        ItemMeta lavaMeta = lavaBucket.getItemMeta();
        if (lavaMeta != null) {
            lavaMeta.setDisplayName(ChatColor.RED + "取消保险");
            List<String> lore = new ArrayList<>();
            lore.add(ChatColor.WHITE + "取消此物品的保险");
            lore.add(ChatColor.RED + "注意：保费不会返还！");
            lore.add("");
            lore.add(ChatColor.YELLOW + "点击此按钮继续");
            lavaMeta.setLore(lore);
            lavaBucket.setItemMeta(lavaMeta);
        }

        ItemStack closeItem = new ItemStack(Material.BARRIER);
        ItemMeta closeMeta = closeItem.getItemMeta();
        if (closeMeta != null) {
            closeMeta.setDisplayName(ChatColor.RED + "返回");
            closeItem.setItemMeta(closeMeta);
        }

        inventory.setItem(11, lavaBucket);
        inventory.setItem(15, closeItem);

        player.openInventory(inventory);
    }

    private void openConfirmGUI(Player player) {
        Inventory inventory = Bukkit.createInventory(null, 27, ChatColor.RED + "确认取消保险");

        ItemStack confirmItem = new ItemStack(Material.LAVA_BUCKET);
        ItemMeta confirmMeta = confirmItem.getItemMeta();
        if (confirmMeta != null) {
            confirmMeta.setDisplayName(ChatColor.RED + "确认取消保险");
            List<String> lore = new ArrayList<>();
            lore.add(ChatColor.WHITE + "你确定要取消保险吗？");
            lore.add(ChatColor.RED + "此操作不可撤销！");
            lore.add(ChatColor.RED + "保费不会返还！");
            lore.add("");
            lore.add(ChatColor.YELLOW + "点击此按钮确认取消");
            confirmMeta.setLore(lore);
            confirmItem.setItemMeta(confirmMeta);
        }

        ItemStack cancelItem = new ItemStack(Material.RED_STAINED_GLASS_PANE);
        ItemMeta cancelMeta = cancelItem.getItemMeta();
        if (cancelMeta != null) {
            cancelMeta.setDisplayName(ChatColor.YELLOW + "返回");
            List<String> lore = new ArrayList<>();
            lore.add(ChatColor.WHITE + "不取消保险");
            cancelMeta.setLore(lore);
            cancelItem.setItemMeta(cancelMeta);
        }

        inventory.setItem(11, confirmItem);
        inventory.setItem(15, cancelItem);

        player.openInventory(inventory);
    }
}
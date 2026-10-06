package com.example.insurance.manager;

import com.example.insurance.InsurancePlugin;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

public class InsuranceManager {

    private final InsurancePlugin plugin;
    private final NamespacedKey INSURANCE_LEVEL_KEY;
    private final NamespacedKey INSURANCE_TIMES_KEY;
    private final NamespacedKey ADMIN_INSURANCE_KEY;
    private final NamespacedKey INSURANCE_PERMIT_KEY;

    public InsuranceManager(InsurancePlugin plugin) {
        this.plugin = plugin;
        this.INSURANCE_LEVEL_KEY = new NamespacedKey(plugin, "insurance_level");
        this.INSURANCE_TIMES_KEY = new NamespacedKey(plugin, "insurance_times");
        this.ADMIN_INSURANCE_KEY = new NamespacedKey(plugin, "admin_insurance");
        this.INSURANCE_PERMIT_KEY = new NamespacedKey(plugin, "insurance_permit");
    }

    public int getInsuranceLevel(ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return 0;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return 0;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        Integer level = container.get(INSURANCE_LEVEL_KEY, PersistentDataType.INTEGER);
        return level != null ? level : 0;
    }

    public int getInsuranceTimes(ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return 0;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return 0;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        Integer times = container.get(INSURANCE_TIMES_KEY, PersistentDataType.INTEGER);
        return times != null ? times : 0;
    }

    public boolean hasAdminInsurance(ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return false;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return false;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        Boolean adminInsurance = container.get(ADMIN_INSURANCE_KEY, PersistentDataType.BOOLEAN);
        return adminInsurance != null && adminInsurance;
    }

    public ItemStack setInsurance(ItemStack item, int level, int times) {
        if (item == null || item.getType() == Material.AIR) {
            return item;
        }

        // 检查投保许可
        if (!isInsurancePermitted(item, level)) {
            return item;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        container.set(INSURANCE_LEVEL_KEY, PersistentDataType.INTEGER, level);
        container.set(INSURANCE_TIMES_KEY, PersistentDataType.INTEGER, times);

        item.setItemMeta(meta);
        return item;
    }

    public ItemStack setAdminInsurance(ItemStack item, boolean adminInsurance) {
        if (item == null || item.getType() == Material.AIR) {
            return item;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        container.set(ADMIN_INSURANCE_KEY, PersistentDataType.BOOLEAN, adminInsurance);

        if (adminInsurance) {
            container.set(INSURANCE_TIMES_KEY, PersistentDataType.INTEGER, Integer.MAX_VALUE);
        }

        item.setItemMeta(meta);
        return item;
    }

    public ItemStack decreaseInsuranceTimes(ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return item;
        }

        if (hasAdminInsurance(item)) {
            return item;
        }

        int currentLevel = getInsuranceLevel(item);
        if (currentLevel == 0) {
            return item;
        }

        int currentTimes = getInsuranceTimes(item);
        if (currentTimes <= 1) {
            ItemMeta meta = item.getItemMeta();
            if (meta == null) {
                return item;
            }

            PersistentDataContainer container = meta.getPersistentDataContainer();
            container.remove(INSURANCE_LEVEL_KEY);
            container.remove(INSURANCE_TIMES_KEY);
            container.remove(ADMIN_INSURANCE_KEY);

            item.setItemMeta(meta);
            return item;
        }

        return setInsurance(item, currentLevel, currentTimes - 1);
    }

    public ItemStack addInsurance(ItemStack item, int level, int times) {
        if (times <= 0 || level < 1 || level > 2) {
            return item;
        }

        return setInsurance(item, level, times);
    }

    public ItemStack upgradeInsurance(ItemStack item) {
        int currentLevel = getInsuranceLevel(item);
        if (currentLevel != 1) {
            return item;
        }

        return setInsurance(item, 2, getInsuranceTimes(item));
    }

    public boolean canStack(ItemStack item1, ItemStack item2) {
        if (item1 == null || item2 == null) {
            return false;
        }

        if (item1.getType() != item2.getType()) {
            return false;
        }

        int level1 = getInsuranceLevel(item1);
        int level2 = getInsuranceLevel(item2);

        if (level1 != level2) {
            return false;
        }

        if (hasAdminInsurance(item1) != hasAdminInsurance(item2)) {
            return false;
        }

        return true;
    }

    public void sendInsuranceExpiredMessage(Player player, ItemStack item) {
        String itemName = item.getType().toString().replace("_", " ").toLowerCase();
        String message = plugin.getConfigManager().getMessage("insurance_expired", itemName);
        player.sendMessage(message);
    }

    public ItemStack removeInsurance(ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return item;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        container.remove(INSURANCE_LEVEL_KEY);
        container.remove(INSURANCE_TIMES_KEY);
        container.remove(ADMIN_INSURANCE_KEY);

        item.setItemMeta(meta);
        return item;
    }

    /**
     * 检查物品是否允许指定等级的保险
     * @param item 要检查的物品
     * @param level 保险等级 (0, 1 或 2)
     * @return 如果允许返回 true，否则返回 false
     */
    public boolean isInsurancePermitted(ItemStack item, int level) {
        if (item == null || item.getType() == Material.AIR) {
            return false;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return false;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        String permit = container.get(INSURANCE_PERMIT_KEY, PersistentDataType.STRING);

        // 如果没有设置投保许可，默认允许
        if (permit == null || permit.isEmpty()) {
            return true;
        }

        // 如果设置为 "forbidden"，禁止所有保险和备份
        if (permit.equals("forbidden")) {
            return false;
        }

        // 如果设置为 "level1"，只允许等级1的保险
        if (permit.equals("level1")) {
            return level == 1;
        }

        // 如果设置为 "level2"，只允许等级2的保险
        if (permit.equals("level2")) {
            return level == 2;
        }

        // 如果设置为 "all"，允许所有等级的保险
        if (permit.equals("all")) {
            return true;
        }

        return false;
    }

    /**
     * 检查物品是否可以被备份（是否允许任何形式的保险）
     * @param item 要检查的物品
     * @return 如果可以被备份返回 true，否则返回 false
     */
    public boolean canBeBackedUp(ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return false;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return false;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        String permit = container.get(INSURANCE_PERMIT_KEY, PersistentDataType.STRING);

        // 如果没有设置投保许可，默认可以备份
        if (permit == null || permit.isEmpty()) {
            return true;
        }

        // 如果设置为 "forbidden"，禁止备份
        if (permit.equals("forbidden")) {
            return false;
        }

        // 其他情况都可以备份
        return true;
    }

    /**
     * 设置物品的投保许可
     * @param item 要设置的物品
     * @param permitType 许可类型 ("permit" 或 "forbid")
     * @param level 保险等级 ("level1", "level2" 或 "all")
     * @return 修改后的物品
     */
    public ItemStack setInsurancePermit(ItemStack item, String permitType, String level) {
        if (item == null || item.getType().isAir()) {
            return item;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();

        if (permitType.equals("forbid")) {
            if (level.equals("level1")) {
                // 禁止 level1，只允许 level2
                container.set(INSURANCE_PERMIT_KEY, PersistentDataType.STRING, "level2");
            } else if (level.equals("level2")) {
                // 禁止 level2，只允许 level1
                container.set(INSURANCE_PERMIT_KEY, PersistentDataType.STRING, "level1");
            } else if (level.equals("all")) {
                // 禁止所有等级
                container.set(INSURANCE_PERMIT_KEY, PersistentDataType.STRING, "forbidden");
            }
        } else {
            // permit 命令
            container.set(INSURANCE_PERMIT_KEY, PersistentDataType.STRING, level);
        }

        item.setItemMeta(meta);
        return item;
    }

    /**
     * 清除物品的投保许可设置
     * @param item 要清除的物品
     * @return 修改后的物品
     */
    public ItemStack clearInsurancePermit(ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return item;
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        container.remove(INSURANCE_PERMIT_KEY);

        item.setItemMeta(meta);
        return item;
    }

    /**
     * 获取物品的投保许可状态
     * @param item 要检查的物品
     * @return 投保许可状态字符串
     */
    public String getInsurancePermit(ItemStack item) {
        if (item == null || item.getType() == Material.AIR) {
            return "none";
        }

        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return "none";
        }

        PersistentDataContainer container = meta.getPersistentDataContainer();
        String permit = container.get(INSURANCE_PERMIT_KEY, PersistentDataType.STRING);
        return permit != null ? permit : "none";
    }
}
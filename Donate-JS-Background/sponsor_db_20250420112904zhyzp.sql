-- MySQL dump 10.13  Distrib 8.4.4, for Linux (x86_64)
--
-- Host: localhost    Database: sponsor_db
-- ------------------------------------------------------
-- Server version	8.4.4

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `sponsor_summary`
--

DROP TABLE IF EXISTS `sponsor_summary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sponsor_summary` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `recipient` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `total_amount` decimal(10,2) NOT NULL DEFAULT '0.00',
  `last_updated` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_recipient` (`username`,`recipient`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sponsor_summary`
--

LOCK TABLES `sponsor_summary` WRITE;
/*!40000 ALTER TABLE `sponsor_summary` DISABLE KEYS */;
INSERT INTO `sponsor_summary` VALUES (1,'cdpyx','cdpyx',5.00,'2025-01-29 06:46:36'),(2,'Titan_hao','BSC',5.00,'2025-01-29 09:49:41');
/*!40000 ALTER TABLE `sponsor_summary` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sponsors`
--

DROP TABLE IF EXISTS `sponsors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sponsors` (
  `id` int NOT NULL AUTO_INCREMENT,
  `order_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `recipient` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `status` enum('pending','completed','failed') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'pending',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `order_id` (`order_id`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sponsors`
--

LOCK TABLES `sponsors` WRITE;
/*!40000 ALTER TABLE `sponsors` DISABLE KEYS */;
INSERT INTO `sponsors` VALUES (1,'ORDER1738071893535mwz5p','','BSC',5.00,'pending','2025-01-28 13:44:53'),(2,'ORDER1738072581516hzf4d','','cdpyx',5.00,'pending','2025-01-28 13:56:21'),(3,'ORDER1738073779683jzqyx','','cdpyx',5.00,'pending','2025-01-28 14:16:19'),(4,'ORDER1738077062206odiyk','','BSC',6.00,'pending','2025-01-28 15:11:02'),(5,'ORDER1738077119033w8gjx','','cdpyx',6.00,'pending','2025-01-28 15:11:59'),(6,'ORDER1738078005832d9nwm','','bus',6.00,'pending','2025-01-28 15:26:45'),(7,'ORDER17380781801261gcy2','','bus',6.00,'pending','2025-01-28 15:29:40'),(8,'ORDER1738079332540ydarx','','cdpyx',5.00,'pending','2025-01-28 15:48:52'),(9,'ORDER1738084589593on4ol','','cdpyx',5.00,'pending','2025-01-28 17:16:29'),(10,'ORDER1738129901631s8gip','','cdpyx',5.00,'pending','2025-01-29 05:51:41'),(11,'ORDER1738132989686w4jif','','cdpyx',5.00,'pending','2025-01-29 06:43:09'),(12,'ORDER17381330684927puyj','','cdpyx',5.00,'pending','2025-01-29 06:44:28'),(15,'ORDER1738144151343r6gbn','cdpyx','BSC',5.00,'pending','2025-01-29 09:49:11'),(16,'ORDER1738155687365gxpc2','Bu7eneChen','bus',5.00,'pending','2025-01-29 13:01:27'),(17,'ORDER1738157393381kwsu0','zzh','cdpyx',10.00,'pending','2025-01-29 13:29:53'),(18,'ORDER1743334147109r00cw','','BSC',6.00,'pending','2025-03-30 11:29:07'),(19,'ORDER17439412483894qewi','','BSC',6.00,'pending','2025-04-06 12:07:28');
/*!40000 ALTER TABLE `sponsors` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-04-20 11:29:04

CREATE TABLE IF NOT EXISTS `uri_addresses` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `uri` varchar(255) NOT NULL,
  `address` varchar(45) NOT NULL,
  `generatedaddress` varchar(45) NULL,
  `status` tinyint(4) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `notifications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `uri` varchar(255) NOT NULL,
  `notificationuri` varchar(255) NOT NULL,
  `authcode` varchar(255) NULL,
  `expiretime` datetime NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `requests` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `requesttime` DATETIME NOT NULL,
  `ipaddress` varchar(50) NULL,
  `uri` varchar(255) NOT NULL,
  `method` varchar(10) NOT NULL,
  `result` varchar(255) NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
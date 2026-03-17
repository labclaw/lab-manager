# 库存生命周期 — high-frequency daily operations
Feature: Inventory Lifecycle
  As a lab scientist at the lab
  I want to manage inventory items through their full lifecycle
  So that I always know what reagents we have, where they are, and when they expire

  Background:
    Given a vendor "Thermo Fisher Scientific" exists
    And a product "Trypsin 0.25%" with catalog "25200056" from that vendor
    And an inventory item with quantity 10 bottles lot "LOT-2026-001"

  # 收货入库
  Scenario: Receive new inventory from an order
    Given an order "PO-12345" for the vendor
    And the order has item "Trypsin 0.25%" quantity 5 unit "bottle"
    When I receive the order
    Then the order status should be "received"

  # 消耗试剂
  Scenario: Consume reagent from inventory
    When I consume 3 bottles from the inventory item with note "Cell culture passage"
    Then the inventory item quantity should be 7
    And a consumption log entry should exist with action "consume" and quantity 3

  # 消耗超过库存
  Scenario: Cannot consume more than available
    When I try to consume 20 bottles from the inventory item
    Then the request should fail with status 422
    And the inventory item quantity should still be 10

  # 转移位置
  Scenario: Transfer inventory between locations
    When I transfer the inventory item to a new location
    Then a consumption log entry should exist with action "transfer"

  # 调整库存（盘点修正）
  Scenario: Adjust inventory after physical count
    When I adjust the inventory item to 8 bottles with reason "Physical count correction"
    Then the inventory item quantity should be 8
    And a consumption log entry should exist with action "adjust"

  # 处置过期试剂
  Scenario: Dispose of expired reagent
    When I dispose of the inventory item with reason "Expired 2026-03-01"
    Then the inventory item status should be "disposed"
    And a consumption log entry should exist with action "dispose"

  # 打开新瓶
  Scenario: Open a sealed item
    When I open the inventory item
    Then the inventory item status should be "opened"
    And a consumption log entry should exist with action "open"

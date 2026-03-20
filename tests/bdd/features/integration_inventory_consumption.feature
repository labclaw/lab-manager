Feature: Integration Inventory Consumption
  As a lab scientist
  I want to consume inventory for experiments
  So that inventory levels stay accurate

  Background:
    Given I am authenticated as "scientist"
    And product "Reagent X" exists
    And inventory exists:
      | product_id | quantity | lot_number |
      | 1          | 100      | LOT-001    |

  Scenario: Consume from single lot
    When I consume 20 units from lot "LOT-001"
    Then inventory should have 80 units
    And audit log should record consumption

  Scenario: Consume from multiple lots FIFO
    Given additional inventory:
      | lot_number | quantity | expires_at  |
      | LOT-002    | 50       | 2025-06-30  |
      | LOT-003    | 50       | 2025-12-31  |
    When I consume 70 units
    Then consumption should use:
      | lot_number | amount |
      | LOT-001    | 50     |
      | LOT-002    | 20     |

  Scenario: Consume with experiment reference
    When I consume 10 units for experiment "EXP-001"
    Then consumption should reference "EXP-001"
    And experiment should show material usage

  Scenario: Consume below reorder level
    Given product has reorder_level 50
    When I consume 60 units
    Then inventory should be 40
    And low_stock alert should be created

  Scenario: Consume more than available
    When I try to consume 150 units
    Then consumption should fail
    And error should indicate insufficient quantity

  Scenario: Consume expired inventory
    Given inventory with lot "LOT-OLD" expired yesterday
    When I try to consume from "LOT-OLD"
    Then consumption should be rejected
    And error should indicate expired inventory

  Scenario: Transfer between locations
    Given locations "Lab A" and "Lab B" exist
    And inventory is in "Lab A"
    When I transfer 30 units to "Lab B"
    Then Lab A should have 70 units
    And Lab B should have 30 units
    And audit log should record transfer

  Scenario: Consume by staff member
    When I consume 5 units
    Then consumption should be attributed to me
    And staff activity should be updated

  Scenario: Bulk consumption
    Given inventory items for 3 products
    When I consume from all 3 products
    Then all inventories should be updated
    And single audit entry should be created

  Scenario: Consumption with waste tracking
    When I consume 10 units and report 2 units wasted
    Then inventory should decrease by 12
    And waste should be tracked separately

  Scenario: Return unused inventory
    Given I previously consumed 20 units
    When I return 10 unused units
    Then inventory should increase by 10
    And return should be logged

  Scenario: Reserve inventory for experiment
    When I reserve 30 units for "EXP-002"
    Then 30 units should be reserved
    And available quantity should be 70
    When I consume reserved inventory
    Then reservation should be fulfilled

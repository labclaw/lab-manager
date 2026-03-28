# Safety Alerts — PPE requirements, waste disposal, and consumption reminders
Feature: Safety Alerts with PPE Warnings
  As a lab manager
  I want PPE recommendations and safety reminders when working with hazardous chemicals
  So that I can protect lab personnel and follow proper safety protocols

  # PPE for flammable chemicals
  Scenario: Get PPE requirements for flammable chemical
    Given a product with hazard info "H225 Highly flammable liquid"
    When I request PPE requirements for that product
    Then the response should contain "Use in fume hood"
    And the response should contain "no open flames"
    And the response should contain "fire-resistant lab coat"
    And the response should contain "safety goggles"

  # PPE for corrosive chemicals
  Scenario: Get PPE requirements for corrosive chemical
    Given a product with hazard info "H314 Causes severe skin burns"
    When I request PPE requirements for that product
    Then the response should contain "Acid-resistant gloves"
    And the response should contain "face shield"
    And the response should contain "chemical apron"

  # PPE for multiple hazard codes
  Scenario: Get PPE requirements for chemical with multiple hazards
    Given a product with hazard info "H225 H314 H331"
    When I request PPE requirements for that product
    Then the response should contain PPE items from multiple hazard categories
    And the response hazard codes should be "H225", "H314", "H331"

  # Safety reminder on hazardous item consumption
  Scenario: Safety reminder on hazardous item consumption
    Given a hazardous product "Acetone" with hazard info "H225 H319"
    And an inventory item for that product with quantity 100
    When I consume 10 units of that item
    Then the response should include a safety reminder
    And the safety reminder should contain PPE requirements

  # No safety reminder for non-hazardous items
  Scenario: No safety reminder for non-hazardous consumption
    Given a non-hazardous product "Sodium Chloride"
    And an inventory item for that product with quantity 500
    When I consume 50 units of that item
    Then the response should not include a safety reminder

  # Inventory safety scan
  Scenario: Inventory safety scan detects missing hazard info
    Given a hazardous product "Sulfuric Acid" with no hazard info
    When I run the inventory safety scan
    Then the scan should return a warning about missing hazard info
    And the warning should reference "Sulfuric Acid"

  # Inventory safety scan - missing CAS
  Scenario: Inventory safety scan detects missing CAS number
    Given a hazardous product "Hydrochloric Acid" with hazard info "H314" but no CAS number
    When I run the inventory safety scan
    Then the scan should return a warning about missing CAS number

  # Unknown hazard codes
  Scenario: Get PPE for unknown hazard code
    When I request PPE requirements for hazard code "H999"
    Then the response should suggest consulting SDS

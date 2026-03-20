Feature: Location Management
  As a lab manager
  I want to manage storage locations
  So that I can track where inventory is stored

  Background:
    Given I am authenticated as "admin"

  Scenario: Create a new location
    When I create a location with:
      | name      | Freezer A-1        |
      | type      | freezer            |
      | capacity  | 100                |
    Then the location should be created
    And the location ID should be returned

  Scenario: List all locations
    Given 5 locations exist
    When I request all locations
    Then I should receive 5 locations
    And each location should have name and type

  Scenario: Update location details
    Given a location "Freezer A" exists
    When I update the location with name "Freezer A-Updated"
    Then the location name should be updated

  Scenario: Delete empty location
    Given a location "Empty Shelf" exists
    And no inventory is in the location
    When I delete the location
    Then the location should be removed

  Scenario: Cannot delete location with inventory
    Given a location "Freezer A" exists
    And 5 inventory items are in "Freezer A"
    When I try to delete the location
    Then the request should fail
    And an error should indicate inventory exists

  Scenario: Location capacity tracking
    Given a location with capacity 100 exists
    And 50 items are in the location
    When I request location details
    Then the current usage should be 50
    And available capacity should be 50

  Scenario: Location overflow warning
    Given a location with capacity 10 exists
    And 8 items are in the location
    When I add 5 more items to the location
    Then a capacity warning should be triggered

  Scenario: Search locations by name
    Given locations exist:
      | name       |
      | Freezer A  |
      | Freezer B  |
      | Cabinet 1  |
    When I search locations for "Freezer"
    Then I should receive 2 locations

  Scenario: Location types
    Given locations exist:
      | type     |
      | freezer  |
      | fridge   |
      | cabinet  |
      | shelf    |
    When I filter locations by type "freezer"
    Then I should receive only freezer locations

  Scenario: Location hierarchy
    Given a building "Lab Building" exists
    And a room "Room 101" in building "Lab Building" exists
    And a location "Freezer A" in room "Room 101" exists
    When I request the location hierarchy
    Then I should see the nested structure

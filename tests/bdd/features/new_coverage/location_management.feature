Feature: Location Management
  As a lab manager
  I want to manage storage locations
  So that inventory placement is organized and traceable

  Background:
    Given the database is clean
    And I am authenticated

  Scenario: Create location with all fields
    When I create location with:
      | name        | Freezer A        |
      | type        | freezer          |
      | building    | Building 1       |
      | floor       | 3                |
      | room        | 301              |
      | temperature | -80              |
    Then the response status should be 201
    And location name should be "Freezer A"

  Scenario: Create location with minimal fields
    When I create location with:
      | name | Shelf 1 |
    Then the response status should be 201

  Scenario: Create location with duplicate name
    Given location "Freezer A" exists
    When I create location with name "Freezer A"
    Then the response status should be 409

  Scenario: Create location without name
    When I create location without name
    Then the response status should be 422

  Scenario: Get location by ID
    Given location with ID "loc-123" exists
    When I request location "loc-123"
    Then the response status should be 200
    And location ID should be "loc-123"

  Scenario: Get non-existent location
    When I request location "non-existent-id"
    Then the response status should be 404

  Scenario: List all locations
    Given 30 locations exist
    When I request all locations
    Then the response should contain 30 locations

  Scenario: List locations with pagination
    Given 50 locations exist
    When I request locations with page 1 and page_size 10
    Then the response should contain 10 locations
    And total count should be 50

  Scenario: Filter locations by type
    Given 10 freezers exist
    And 15 refrigerators exist
    And 5 shelves exist
    When I request locations with type "freezer"
    Then the response should contain 10 locations

  Scenario: Filter locations by building
    Given 20 locations in "Building 1" exist
    And 15 locations in "Building 2" exist
    When I request locations in "Building 1"
    Then the response should contain 20 locations

  Scenario: Filter locations by temperature range
    Given 5 frozen locations (-80C) exist
    And 10 cold locations (4C) exist
    And 20 room temp locations exist
    When I request frozen locations
    Then the response should contain 5 locations

  Scenario: Search locations by name
    Given locations "Freezer A-1", "Freezer A-2", "Refrigerator B" exist
    When I search locations for "Freezer A"
    Then the response should contain 2 locations

  Scenario: Update location name
    Given location with name "Old Name" exists
    When I update location name to "New Name"
    Then location name should be "New Name"

  Scenario: Update location temperature
    Given location with temperature -80 exists
    When I update location temperature to -20
    Then location temperature should be -20

  Scenario: Update location capacity
    Given location exists
    When I update location capacity to 100
    Then location capacity should be 100

  Scenario: Delete empty location
    Given location with no inventory exists
    When I delete the location
    Then the response status should be 204
    And the location should no longer exist

  Scenario: Cannot delete location with inventory
    Given location with inventory exists
    When I try to delete the location
    Then the response status should be 400

  Scenario: Get location inventory
    Given location "Freezer A" with 25 items exists
    When I request location inventory
    Then the response should contain 25 items

  Scenario: Get location capacity
    Given location with capacity 100 and 75 items exists
    When I request location details
    Then capacity should be 100
    And used capacity should be 75
    And available capacity should be 25

  Scenario: Location hierarchy - parent child
    Given location "Building 1" exists
    When I create child location "Room 101" under "Building 1"
    Then "Room 101" should be child of "Building 1"

  Scenario: Get child locations
    Given parent location with 5 children exists
    When I request child locations
    Then response should contain 5 locations

  Scenario: Get parent location
    Given child location exists
    When I request parent location
    Then parent location should be returned

  Scenario: Location path
    Given location hierarchy "Building 1 > Floor 2 > Room 201 > Freezer A" exists
    When I request location path
    Then path should be "Building 1 > Floor 2 > Room 201 > Freezer A"

  Scenario: Location barcode
    When I create location with:
      | name     | Shelf B-1  |
      | barcode  | LOC-12345  |
    Then location barcode should be "LOC-12345"

  Scenario: Find location by barcode
    Given location with barcode "LOC-12345" exists
    When I scan barcode "LOC-12345"
    Then correct location should be returned

  Scenario: Location access restrictions
    Given location with restricted access exists
    When unauthorized user requests location
    Then the response status should be 403

  Scenario: Location temperature monitoring
    Given location with temperature monitoring exists
    When I request temperature history
    Then temperature readings should be returned

  Scenario: Location temperature alert
    Given location with temperature range -80 to -70 exists
    When temperature exceeds -70
    Then temperature alert should be created

  Scenario: Location map view
    Given locations across multiple buildings exist
    When I request location map
    Then hierarchical structure should be returned

  Scenario: Bulk create locations
    Given CSV with 20 locations
    When I import locations from CSV
    Then 20 locations should be created

  Scenario: Export locations
    Given 40 locations exist
    When I export locations to CSV
    Then the response content type should be "text/csv"

  Scenario: Location audit trail
    Given location with 5 changes exists
    When I request location history
    Then all changes should be recorded
    And timestamps should be present

  Scenario: Location notes
    Given location exists
    When I add note "Requires key card access"
    Then location note should be recorded

  Scenario: Location contacts
    Given location exists
    When I assign contact person "John Doe"
    Then location should have contact

  Scenario: Location status
    Given active location exists
    When I mark location as maintenance
    Then location status should be "maintenance"
    And inventory should be flagged for relocation

  Scenario: Location sharing
    Given location owned by "Lab A" exists
    When I share location with "Lab B"
    Then "Lab B" should have access to location

  Scenario: Archive location
    Given location with no inventory exists
    When I archive the location
    Then location status should be "archived"
    And location should not appear in active searches

  Scenario: Location statistics
    Given location with varied inventory exists
    When I request location statistics
    Then total items should be reported
    And capacity utilization should be calculated
    And category breakdown should be included

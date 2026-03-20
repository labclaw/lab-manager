Feature: Equipment Management
  As a lab manager
  I want to manage lab equipment
  So that equipment is properly tracked and maintained

  Background:
    Given the database is clean
    And I am authenticated

  Scenario: Create equipment with all fields
    When I create equipment with:
      | name          | Centrifuge Model X |
      | serial_number | SN-2026-001        |
      | location      | Lab Room 101       |
      | status        | operational        |
    Then the response status should be 201
    And equipment name should be "Centrifuge Model X"

  Scenario: Create equipment with minimal fields
    When I create equipment with:
      | name | Basic Pipette |
    Then the response status should be 201

  Scenario: Create equipment with duplicate serial
    Given equipment with serial "SN-2026-001" exists
    When I create equipment with serial "SN-2026-001"
    Then the response status should be 409

  Scenario: Create equipment without name
    When I create equipment without name
    Then the response status should be 422

  Scenario: Get equipment by ID
    Given equipment with ID "equip-123" exists
    When I request equipment "equip-123"
    Then the response status should be 200
    And equipment ID should be "equip-123"

  Scenario: Get non-existent equipment
    When I request equipment "non-existent-id"
    Then the response status should be 404

  Scenario: List all equipment
    Given 15 equipment items exist
    When I request all equipment
    Then the response should contain 15 items

  Scenario: List equipment with pagination
    Given 25 equipment items exist
    When I request equipment with page 1 and page_size 10
    Then the response should contain 10 items
    And total count should be 25

  Scenario: Filter equipment by status
    Given 5 operational equipment exist
    And 3 maintenance equipment exist
    When I request equipment with status "operational"
    Then the response should contain 5 items

  Scenario: Filter equipment by location
    Given 8 equipment in "Lab Room 101" exist
    And 4 equipment in "Lab Room 102" exist
    When I request equipment at location "Lab Room 101"
    Then the response should contain 8 items

  Scenario: Update equipment name
    Given equipment with name "Old Name" exists
    When I update equipment name to "New Name"
    Then the equipment name should be "New Name"

  Scenario: Update equipment status
    Given operational equipment exists
    When I update equipment status to "maintenance"
    Then the equipment status should be "maintenance"

  Scenario: Update equipment location
    Given equipment at location "Room A" exists
    When I move equipment to "Room B"
    Then the equipment location should be "Room B"

  Scenario: Delete equipment
    Given equipment exists with no dependencies
    When I delete the equipment
    Then the response status should be 204
    And the equipment should no longer exist

  Scenario: Cannot delete equipment with maintenance records
    Given equipment with maintenance history exists
    When I try to delete the equipment
    Then the response status should be 400

  Scenario: Add maintenance record
    Given equipment exists
    When I add maintenance record:
      | type        | Calibration     |
      | date        | 2026-03-20      |
      | performed_by| John Doe        |
      | notes       | Annual calibrate|
    Then the response status should be 201
    And maintenance record should be linked to equipment

  Scenario: Get maintenance history
    Given equipment with 5 maintenance records exists
    When I request maintenance history
    Then the response should contain 5 records
    And records should be ordered by date descending

  Scenario: Schedule upcoming maintenance
    Given equipment exists
    When I schedule maintenance for "2026-04-01"
    Then upcoming maintenance date should be "2026-04-01"
    And a reminder should be created

  Scenario: Get equipment due for maintenance
    Given 3 equipment items due for maintenance exist
    And 5 equipment not due exist
    When I request equipment due for maintenance
    Then the response should contain 3 items

  Scenario: Mark maintenance as complete
    Given equipment with scheduled maintenance exists
    When I mark maintenance as complete
    Then maintenance status should be "completed"
    And next maintenance date should be calculated

  Scenario: Equipment calibration expiry
    Given equipment with calibration expiring in 30 days
    When calibration check runs
    Then an alert should be created

  Scenario: Equipment out of calibration
    Given equipment with calibration expired
    When I check equipment status
    Then status should indicate "calibration required"

  Scenario: Search equipment by name
    Given equipment with name containing "Centrifuge" exists
    When I search equipment for "Centrifuge"
    Then matching equipment should be returned

  Scenario: Search equipment by serial
    Given equipment with serial "SN-2026-ABC" exists
    When I search for serial "ABC"
    Then the correct equipment should be returned

  Scenario: Equipment usage log
    Given equipment used 10 times exists
    When I request usage log
    Then response should contain 10 usage records

  Scenario: Record equipment usage
    Given equipment exists
    When I record usage by "user@example.com"
    Then usage count should increment
    And usage record should be created

  Scenario: Equipment warranty tracking
    Given equipment with warranty expiring "2026-12-31"
    When I check warranty status
    Then warranty expiration should be "2026-12-31"

  Scenario: Equipment warranty expired alert
    Given equipment with expired warranty
    When warranty check runs
    Then a warranty expiration alert should be created

  Scenario: Bulk update equipment status
    Given 10 equipment items exist
    When I bulk update status to "retired"
    Then all 10 items should have status "retired"

  Scenario: Equipment depreciation calculation
    Given equipment with purchase price 10000 and age 2 years
    When I request depreciation value
    Then calculated depreciation should be returned

  Scenario: Assign equipment to user
    Given equipment and user exist
    When I assign equipment to user
    Then equipment should have assigned user
    And user should see assigned equipment

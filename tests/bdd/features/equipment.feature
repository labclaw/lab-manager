# Equipment full lifecycle + photo-based AI extraction
Feature: Equipment Lifecycle
  As a lab manager in the lab
  I want to manage lab equipment through their full lifecycle
  So that I know what devices we have, their status, and can track them from photos

  # Register new device
  Scenario: Register new equipment manually
    When I create equipment "Eppendorf 5702R Centrifuge" with category "centrifuge" and manufacturer "Eppendorf"
    Then the equipment should be created with status "active"
    And the equipment name should be "Eppendorf 5702R Centrifuge"
    And the equipment manufacturer should be "Eppendorf"

  # List and paginate
  Scenario: List equipment with pagination
    Given 5 equipment items exist
    When I list equipment with page 1 and page_size 2
    Then I should get 2 equipment items
    And the total count should be 5
    And the page count should be 3

  # Filter by category
  Scenario: Filter equipment by category
    Given equipment "PCR Machine" with category "pcr" exists
    And equipment "Centrifuge A" with category "centrifuge" exists
    And equipment "Centrifuge B" with category "centrifuge" exists
    When I filter equipment by category "centrifuge"
    Then I should get 2 equipment items

  # Filter by status
  Scenario: Filter equipment by status
    Given equipment "Working Scope" with status "active" exists
    And equipment "Broken Laser" with status "broken" exists
    When I filter equipment by status "active"
    Then I should get 1 equipment items

  # Search by name or manufacturer
  Scenario: Search equipment by name or manufacturer
    Given equipment "Bruker Two-Photon" with manufacturer "Bruker" exists
    And equipment "Olympus BX Microscope" with manufacturer "Olympus" exists
    When I search equipment for "Bruker"
    Then I should get 1 equipment items

  # Update details
  Scenario: Update equipment details
    Given equipment "Old Name" with category "microscope" exists
    When I update the equipment name to "Nikon A1R Confocal"
    Then the equipment name should be "Nikon A1R Confocal"

  # Status change
  Scenario: Change equipment status to maintenance
    Given equipment "Scope A" with status "active" exists
    When I update the equipment status to "maintenance"
    Then the equipment status should be "maintenance"

  # Decommission
  Scenario: Decommission equipment
    Given equipment "Old Freezer" with status "active" exists
    When I update the equipment status to "decommissioned"
    Then the equipment status should be "decommissioned"

  # Soft delete
  Scenario: Soft-delete equipment
    Given equipment "To Delete" with category "other" exists
    When I delete the equipment
    Then the equipment status should be "deleted"

  # Get detail by ID
  Scenario: Get equipment detail by ID
    When I create equipment "Bio-Rad ChemiDoc MP" with category "imaging" and manufacturer "Bio-Rad"
    Then I can retrieve the equipment by ID
    And the equipment should have created_at and updated_at timestamps

  # Assign to location
  Scenario: Assign equipment to a location
    Given a storage location "Room 6501E" exists
    When I create equipment "Freezer -80C" with category "freezer" and location "Room 6501E"
    Then the equipment location_id should match the location

  # Photo management
  Scenario: Add photos to equipment
    When I create equipment "Laser System" with category "laser" and manufacturer "Coherent"
    And I update the equipment photos with 2 photo paths
    Then the equipment should have 2 photos

  # VLM extraction traceability
  Scenario: Store VLM-extracted data with traceability
    When I create equipment "Bruker System" with extracted data from VLM
    Then the equipment extracted_data should contain the source model
    And the equipment extracted_data should contain the extraction timestamp
    And the equipment extracted_data should contain the source photo path

Feature: User Experience
  As a lab manager user
  I want a smooth, intuitive interface
  So that I can manage my lab efficiently

  Background:
    Given the system is set up
    And I am logged in as "admin@test.com"

  Scenario: Dashboard loads without errors
    When I navigate to the dashboard
    Then the page should load within 2 seconds
    And I should see the sidebar navigation
    And no console errors should appear

  Scenario: Sidebar navigation works correctly
    Given I am on the dashboard
    When I click the "Documents" nav link
    Then I should be on the documents page
    And the URL should be "/documents"

  Scenario: Dark mode toggle persists
    Given I am on the dashboard in light mode
    When I click the dark mode toggle
    Then the theme should change to dark
    And the preference should be saved
    When I refresh the page
    Then the theme should still be dark

  Scenario: Empty state shows helpful message
    Given no documents exist in the system
    When I navigate to the documents page
    Then I should see an empty state message
    And the message should suggest uploading a document

  Scenario: Form validation shows clear errors
    Given I am on the login page
    When I submit the form with empty fields
    Then I should see validation error messages
    And the errors should be in red text

  Scenario: Search results update as I type
    Given some documents exist
    When I type in the search box
    Then results should filter in real-time
    And the search should be debounced

  Scenario: Pagination shows correct page info
    Given 50 documents exist
    When I navigate to the documents page
    Then I should see page size options
    And the current page should be highlighted
    And total count should be displayed

  Scenario: Responsive layout on mobile
    Given I am on the dashboard
    When I resize to mobile viewport
    Then the sidebar should collapse
    And a hamburger menu should appear

  Scenario: Loading states are visible
    Given slow network conditions
    When I navigate to the inventory page
    Then I should see a loading indicator
    And the indicator should disappear when data loads

  Scenario: Success notifications appear
    Given I am uploading a document
    When the upload completes successfully
    Then a success notification should appear
    And it should auto-dismiss after 3 seconds

  Scenario: Error notifications are dismissible
    Given an API error occurs
    When the error notification appears
    Then I should be able to dismiss it
    And it should have a close button

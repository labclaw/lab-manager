# API 安全 — 输入验证和攻击面回归
Feature: API Security and Input Validation
  As a secure API
  I want supported endpoints to validate hostile input safely
  So that the system remains protected without breaking legitimate use

  Background:
    Given I am authenticated as staff "user1"

  Scenario: SQL injection in product name
    When I create a product with name "'; DROP TABLE products; --"
    Then the product should be created with the literal name
    And no SQL injection should occur

  Scenario: SQL injection in search query
    When I search for "1' OR '1'='1"
    Then the search should be sanitized
    And no data leak should occur

  Scenario: HTML characters in vendor name round-trip safely
    When I create a vendor with name "<script>alert('xss')</script>"
    Then the vendor name should round-trip as raw text
    And the response should be safe JSON

  Scenario: HTML characters in product metadata round-trip safely
    Given product metadata contains "<img src=x onerror=alert(1)>"
    When I request the product details
    Then the description metadata should round-trip as raw text
    And the response should be safe JSON

  Scenario: Path traversal in document path is rejected
    When I create a document with path "../../../etc/passwd"
    Then the request should be rejected
    And no file system access should occur

  Scenario: Upload exceeds size limit
    When I upload a file larger than 50MB
    Then I should receive a 413 Payload Too Large error
    And the error should indicate size limit

  Scenario: Request body too large
    When I send a JSON body larger than 10MB
    Then I should receive a 413 error
    And memory should not be exhausted

  Scenario: Invalid product identifier in path
    When I request product with ID "not-a-number"
    Then I should receive a 422 validation error
    And the error should specify integer format

  Scenario: Negative quantity
    When I create an order item with quantity -5
    Then I should receive a validation error
    And the error should indicate minimum value

  Scenario: Quantity exceeds maximum
    When I create an order item with quantity 1000001
    Then I should receive a validation error
    And the error should indicate maximum value

  Scenario: Rate limit exceeded on login
    Given I have made 5 login attempts in the last minute
    When I make another login attempt
    Then I should receive a 429 Too Many Requests error
    And the response should include retry-after header

  Scenario: CORS headers on preflight
    When I send a proper OPTIONS preflight request
    Then appropriate CORS headers should be returned
    And allowed methods should be listed

  Scenario: Invalid upload content type
    When I upload an XML document to the upload endpoint
    Then I should receive a 400 error
    And the error should indicate unsupported file type

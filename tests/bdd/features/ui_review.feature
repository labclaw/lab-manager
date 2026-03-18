# 审核队列 — 批量审核、逐个审批/拒绝
Feature: Review Queue UI
  As a lab scientist at Shen Lab
  I want to efficiently review and approve/reject documents that need human verification
  So that correct data enters the database and OCR errors are caught

  Background:
    Given I am logged in as a scientist
    And I am on the review queue view

  # 队列显示待审核文件
  @wip
  Scenario: Review queue shows only needs_review documents
    Given 10 documents with status "needs_review"
    And 5 documents with status "approved"
    When the review queue loads
    Then I should see exactly 10 document rows
    And all documents should have status "needs_review"

  # 逐个审批
  @wip
  Scenario: Approve a single document from review queue
    Given a "needs_review" document exists
    When I click on the document row
    And I click "Save & Approve" in the detail panel
    Then I should see a success toast "Document approved"
    And the document should disappear from the review queue

  # 逐个拒绝并填写原因
  @wip
  Scenario: Reject a document with reason
    Given a "needs_review" document exists
    When I click on the document row
    And I click "Reject" in the detail panel
    Then a rejection reason modal should appear
    When I enter reason "Duplicate scan, poor quality"
    And I click "Reject" in the modal
    Then I should see a success toast "Document rejected"
    And the document should disappear from the review queue

  # 批量选择
  @wip
  Scenario: Select multiple documents with checkboxes
    Given 5 "needs_review" documents exist
    When I check the checkbox on document 1
    And I check the checkbox on document 3
    And I check the checkbox on document 5
    Then the bulk action bar should show "3 selected"
    And the "Approve Selected" button should be visible
    And the "Reject Selected" button should be visible

  # 全选
  @wip
  Scenario: Select all documents in review queue
    Given 5 "needs_review" documents exist
    When I click the "Select All" checkbox
    Then all 5 checkboxes should be checked
    And the bulk action bar should show "5 selected"

  # 取消全选
  @wip
  Scenario: Deselect all clears selection
    Given 5 "needs_review" documents are all selected
    When I click the "Select All" checkbox to uncheck
    Then no checkboxes should be checked
    And the bulk action bar should be hidden

  # 批量审批
  @wip
  Scenario: Bulk approve selected documents
    Given 3 "needs_review" documents are selected
    When I click "Approve Selected"
    Then I should see a confirmation dialog "Approve 3 documents?"
    When I confirm
    Then I should see a progress indicator
    And after completion I should see a success toast "3 documents approved"
    And the review queue should show 0 documents

  # 批量拒绝
  @wip
  Scenario: Bulk reject selected documents
    Given 2 "needs_review" documents are selected
    When I click "Reject Selected"
    Then a bulk rejection reason modal should appear
    When I enter reason "Illegible scans"
    And I confirm the bulk rejection
    Then I should see a success toast "2 documents rejected"

  # 空队列
  @wip
  Scenario: Empty review queue shows helpful message
    Given 0 documents with status "needs_review"
    When the review queue loads
    Then I should see an empty state message "No documents need review"
    And the bulk action bar should be hidden

  # 部分批量失败
  @wip
  Scenario: Bulk approve handles partial failure gracefully
    Given 3 "needs_review" documents are selected
    And 1 of them was already approved by another user
    When I click "Approve Selected" and confirm
    Then I should see a summary toast "2 approved, 1 failed"
    And the failed document should remain in the queue

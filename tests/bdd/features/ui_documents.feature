# 文件管理界面 — 列表、筛选、内联编辑、审批
Feature: Document Management UI
  As a lab scientist at Shen Lab
  I want to browse, search, and edit extracted document data in the browser
  So that I can correct OCR errors before approving documents into the system

  Background:
    Given I am logged in as a scientist
    And I am on the documents view

  # 文件列表
  @wip
  Scenario: Documents list shows paginated results
    Given 50 documents exist
    When the documents view loads
    Then I should see a table with up to 30 document rows
    And each row should show ID, filename, vendor, type, status, and confidence
    And I should see pagination showing "Page 1 of 2"

  # 状态筛选
  @wip
  Scenario Outline: Filter documents by status
    Given 10 documents with status "approved"
    And 5 documents with status "needs_review"
    And 2 documents with status "rejected"
    When I click the "<filter>" filter button
    Then only documents with status "<status>" should be displayed

    Examples:
      | filter       | status       |
      | Approved     | approved     |
      | Needs Review | needs_review |
      | Rejected     | rejected     |

  # 恢复全部
  @wip
  Scenario: Clear filter shows all documents
    Given I have the "Approved" filter active
    When I click the "All" filter button
    Then all documents should be displayed regardless of status

  # 搜索功能
  @wip
  Scenario: Search documents by vendor name
    Given a document from vendor "Thermo Fisher" exists
    When I type "thermo" in the search input
    And I wait for the debounce period
    Then the document list should filter to show only matching results

  # 打开详情面板
  @wip
  Scenario: Click document row opens detail panel
    Given documents exist
    When I click on a document row
    Then the detail side panel should slide open
    And it should show the scan image
    And it should show extracted document info fields
    And it should show line items if present

  # 关闭详情面板
  @wip
  Scenario: Close detail panel with X button or Escape
    Given the detail panel is open for a document
    When I press the Escape key
    Then the detail panel should close
    And the overlay should disappear

  # 内联编辑 — 修改供应商
  @wip
  Scenario: Edit extracted vendor name before approval
    Given a "needs_review" document with vendor "Fihser Scientific" exists
    When I open the document detail
    And I click the "Edit" button
    And I change the vendor field to "Fisher Scientific"
    Then the vendor field should show "Fisher Scientific"
    And the field should be highlighted as edited

  # 内联编辑 — 修改行项目
  @wip
  Scenario: Edit line item quantity in detail panel
    Given a "needs_review" document with 2 line items exists
    When I open the document detail
    And I click the "Edit" button
    And I change item 1 quantity to "5"
    Then item 1 should show quantity "5"

  # 内联编辑 — 添加行项目
  @wip
  Scenario: Add a new line item to extracted data
    Given a "needs_review" document with 1 line item exists
    When I open the document detail in edit mode
    And I click "Add Row"
    And I fill in catalog "NEW-001" description "New Reagent" quantity "2"
    Then the line items table should show 2 rows

  # 内联编辑 — 删除行项目
  @wip
  Scenario: Remove a line item from extracted data
    Given a "needs_review" document with 3 line items exists
    When I open the document detail in edit mode
    And I click the delete button on item 2
    Then the line items table should show 2 rows
    And item 2 should no longer be visible

  # 保存并审批
  @wip
  Scenario: Save edits and approve document
    Given a "needs_review" document with vendor "Fihser" exists
    When I open the document detail
    And I edit the vendor to "Fisher Scientific"
    And I click "Save & Approve"
    Then I should see a success toast "Document approved"
    And the document status should change to "approved"
    And the detail panel should close

  # 取消编辑
  @wip
  Scenario: Cancel edits reverts to original data
    Given a "needs_review" document with vendor "Original Vendor" exists
    When I open the document detail
    And I edit the vendor to "Wrong Vendor"
    And I click "Cancel"
    Then the vendor field should show "Original Vendor"

  # 翻页
  @wip
  Scenario: Pagination navigates between pages
    Given 60 documents exist
    When I click the "Next" pagination button
    Then I should see "Page 2 of 2"
    And the document list should show different documents
    When I click the "Prev" pagination button
    Then I should see "Page 1 of 2"

  # 已审批文件只读
  @wip
  Scenario: Approved documents show read-only detail
    Given an "approved" document exists
    When I open the document detail
    Then I should not see an "Edit" button
    And I should see the status badge "approved"
    And I should see who reviewed it

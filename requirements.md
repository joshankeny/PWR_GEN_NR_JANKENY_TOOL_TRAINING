# Business Requirements Document

## Tool Identification & Training Application

### Project Overview

Develop a web-based application that helps apprentices and other employees identify tools, understand their purpose, and determine the correct tool for a given work scenario. The application should support training, improve tool recognition, and reduce common mistakes made during the apprenticeship program.

---

# Business Objective

Provide an accessible, maintainable training platform that:

* Improves apprentice familiarity with tools.
* Assists with Civil Service Exam preparation.
* Provides scenario-based learning.
* Allows training content to be updated without requiring software redevelopment.
* Supports future expansion into additional equipment categories.

---

# Stakeholders

| Stakeholder         | Role                          |
| ------------------- | ----------------------------- |
| Emily Wood          | Content Owner / Administrator |
| Apprentices         | Primary Users                 |
| Training Department | Business Owner                |
| Josh Ankeny         | Support                       |

---

# Target Users

* New apprentices
* Existing apprentices
* Employees seeking refresher training
* Individuals preparing for Civil Service examinations

---

# Functional Requirements

## Tool Library

The system shall maintain a catalog of tools.

Each tool should contain:

* Unique Tool ID
* Formal Name
* Common Name
* Description
* Tool Family
* Typical Storage Location
* Difficulty Rating
* Photo/Image

Example attributes:

| Field            | Description                     |
| ---------------- | ------------------------------- |
| Tool ID          | Unique identifier               |
| Formal Name      | Official tool name              |
| Common Name      | Everyday name                   |
| Use Description  | Purpose of the tool             |
| Tool Family      | Screwdrivers, Pliers, etc.      |
| Storage Location | Body, Toolbox, Truck, Warehouse |
| Difficulty       | Scale from 1–10                 |
| Photo            | Reference image                 |

---

## Tool Identification

For every tool the application shall answer:

* What is this tool?
* What does it do?
* When should it be used?
* In this scenario, is this the correct tool?

---

## Scenario-Based Learning

The application shall include work scenarios that recommend one or more appropriate tools.

---

## Tool Families

The application shall organize tools into logical families.

Examples include:

* Screwdrivers
* Pliers
* Wrenches
* Cutting Tools

Users should be able to browse or filter by family.

---

## Commonly Missed Tools

The application should support highlighting tools that are frequently missed during training.

Possible features include:

* User option to enable/disable emphasis on missed tools.
* Administrator option to require repeated exposure to commonly missed tools.

---

## Tool Search

Users should be able to search by:

* Tool name
* Common name
* Tool family
* Scenario

---

## Training Progress

The system should track learner progress, including:

* Completed tools
* Viewed scenarios
* Quiz completion
* Overall progress

---

## Content Management

Training staff should be able to:

* Add new tools
* Edit tool descriptions
* Update images
* Modify scenarios

Content updates should not require application redevelopment or republishing.

---

# Data Requirements

## Tool Dataset

Required fields include:

* Tool ID
* Formal Name
* Common Name
* Description
* Family
* Storage Location
* Difficulty
* Image

---

## Scenario Dataset

Required fields include:

* Scenario Name
* Recommended Tool IDs
* Optional Notes

---

# Non-Functional Requirements

## Accessibility

The application shall be accessible to:

* Apprentices
* Experienced electrical workers
* Desktop users
* Mobile users

---

## Platform

The application shall support:

* Web browsers
* Mobile devices
* Desktop computers

---

## Maintainability

Training administrators should be able to maintain all content without developer assistance.

---

## Learning Management System Integration

The solution should support integration with an LMS.

Potential standards include:

* xAPI
* SCORM

Potential LMS:

* Docebo

---

# Existing Questions

The project team should determine:

* Are tool functions already documented?
* Are work scenarios already documented?
* What existing training material can be reused?
* How should commonly missed tools be identified?
* How should training completion be measured?

---

# Future Enhancements

Potential future phases include:

* Vehicle identification training
* Trailer identification training
* Expanded equipment catalog
* Additional scenario libraries
* Enhanced analytics and reporting
* Preparation for the 2027 Apprentice Class

---

# Assumptions

* Emily will serve as the primary content administrator.
* Initial scope is focused on hand tools.
* The application will primarily support apprentice training but may later expand to additional employee groups.
* Existing training videos may be imported into the learning platform.

---

# Success Criteria

The project will be considered successful if:

* Apprentices can correctly identify tools and their uses.
* Users can determine the correct tool for common work scenarios.
* Training staff can independently update content.
* The application integrates with the organization's learning platform.
* The system provides measurable improvements in apprentice training outcomes.

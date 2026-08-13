Feature: Search offers and demands
  Scenario: Searching across multiple offers and demands
    Given the database has multiple offers and demands with administrative locations and addresses
    When I search for "water" in offers and demands
    Then the search results include an offer for "Clean water available"
    And the search results include a demand for "Need water filters"
    And the search results do not include "Need medical supplies"
    When I search for "Chapinero" in offers and demands
    Then the search results include an offer for "Clean water available"
    And the search results include a demand for "Need water filters"
    When I search for "Community Center" in offers and demands
    Then the search results include an offer for "Clean water available"


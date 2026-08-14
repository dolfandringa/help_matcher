Feature: WhatsApp chatbot conversation
  Scenario: Creating and closing a demand through the chatbot
    Given a WhatsApp user is chatting with the bot
    When the user says "Necesito agua y comida en Cali"
    Then the bot asks the user to confirm a demand
    When the user says "sí"
    Then a demand is created with public id "D1"
    And the bot tells the user how to close "D1"
    When the user says "cerrar D1"
    Then the bot asks the user to confirm closing "D1"
    When the user says "sí"
    Then demand "D1" is closed

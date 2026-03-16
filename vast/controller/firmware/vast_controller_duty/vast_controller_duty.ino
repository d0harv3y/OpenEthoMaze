/*
 * VAST Controller - Duty cycle vibration (no LINX).
 * Listens for serial commands: D<0-100>\n to set PWM duty on the vibration pin.
 * On-board LED (pin 13) brightness mirrors duty via software PWM.
 * Pin 7: manual button (to GND) sends T\n to PC to trigger start trial.
 *
 * Wiring: PWM pin 9 -> vibration motor driver. Pin 7 -> button -> GND.
 */

const int VIBE_PIN = 9;   // PWM pin for vibration
const int LED_PIN = 13;   // On-board LED (software PWM; pin 13 is not hardware PWM on Uno)
const int BUTTON_PIN = 7; // Manual start-trial button (INPUT_PULLUP: press = LOW)
const int BAUDRATE = 9600;

const unsigned long LED_PERIOD_MS = 100;  // Software PWM period for LED
const unsigned long DEBOUNCE_MS = 50;

int currentDuty = 0;  // 0-100
const int MIN_DUTY = 0;
const int MAX_DUTY = 100;

unsigned long ledCycleStart = 0;
int lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
int lastStableButtonState = HIGH;

void setup() {
  Serial.begin(BAUDRATE);
  pinMode(VIBE_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  analogWrite(VIBE_PIN, 0);
  digitalWrite(LED_PIN, LOW);
}

void loop() {
  // 1) Serial: D<0-100>\n or ?\n (identity: respond VAST_CONTROLLER_DUTY)
  if (Serial.available()) {
    int c = Serial.read();
    if (c == 'D') {
      int val = Serial.parseInt();
      if (val >= MIN_DUTY && val <= MAX_DUTY) {
        currentDuty = val;
        int pwm = map(currentDuty, 0, 100, 0, 255);
        analogWrite(VIBE_PIN, pwm);
      }
      while (Serial.available() && Serial.read() != '\n') {}
    } else if (c == '?') {
      while (Serial.available() && Serial.read() != '\n') {}
      Serial.println("VAST_CONTROLLER_DUTY");
    } else {
      while (Serial.available() && Serial.read() != '\n') {}
    }
  }

  // 2) Button on pin 7: debounce and send T\n on press
  int readButton = digitalRead(BUTTON_PIN);
  if (readButton != lastButtonState) {
    lastDebounceTime = millis();
  }
  if ((millis() - lastDebounceTime) > DEBOUNCE_MS) {
    if (readButton != lastStableButtonState) {
      lastStableButtonState = readButton;
      if (lastStableButtonState == LOW) {
        Serial.print("T\n");
      }
    }
  }
  lastButtonState = readButton;

  // 3) Software PWM for LED on pin 13 (mirror duty brightness)
  unsigned long now = millis();
  if (ledCycleStart == 0) {
    ledCycleStart = now;
  }
  unsigned long elapsed = now - ledCycleStart;
  if (elapsed >= LED_PERIOD_MS) {
    ledCycleStart = now;
    elapsed = 0;
  }
  unsigned long onTime = (LED_PERIOD_MS * (unsigned long)currentDuty) / 100;
  if (elapsed < onTime) {
    digitalWrite(LED_PIN, HIGH);
  } else {
    digitalWrite(LED_PIN, LOW);
  }
}

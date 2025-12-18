#include <CD74HC4067.h>

#include <FastLED.h>

#define NUM_SENSORS 64
#define DATA_PIN 4
#define SIGNAL_PIN A3
#define DEBOUNCE_MS 50
#define CMD_BUFFER 32

int biasthing = 40;

int readingsperreading = 2;

const byte numBytes = 64*3;
byte receivedBytes[numBytes];
byte numReceived = 0;

CD74HC4067 mux(8, 9, 10, 11); 
CRGB leds[NUM_SENSORS];

const int enPins[4] = {2, 3, 5, 6};

char stableStates[NUM_SENSORS];    
char lastRawStates[NUM_SENSORS];   
unsigned long lastChangeTime[NUM_SENSORS];

char receivedChars[CMD_BUFFER];
bool newData = false;

const char START_CHAR = '<';
const char END_CHAR = '>';
int averageReading = 0;
int sensitivity = 30;
int north_thresh = 30;
int south_thresh = 30;

bool ledThisLoop = false;

char recievedLedData;

void setup() {
  Serial.begin(500000);
  pinMode(SIGNAL_PIN, INPUT);

  for (int i = 0; i < 4; i++) {
    pinMode(enPins[i], OUTPUT);
    digitalWrite(enPins[i], HIGH);
  }

  FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, 64);

  for (int i = 0; i < NUM_SENSORS; i++) {
    stableStates[i] = lastRawStates[i] = 'z';
    lastChangeTime[i] = 0;
  }

  calibrateSensors();
}

struct Command {
  const char* name;
  void (*func)();
};

Command commands[] = {
  {"?states?", sendStates},
  {"calibrate", calibrateSensors},
  {"?sensitivity?", sendCurrentSensitivity},
  {"?north_thresh?", sendCurrentnorth_thresh},
  {"?south_thresh?", sendCurrentsouth_thresh},
  {"?average?", sendAverage},
  {"led values coming", prepForLed},
};

void loop() {
  if (ledThisLoop) {
    recvBytesWithStartEndMarkers();
    if (newData == true) {
      for (int i = 0; i < numReceived && i / 3 < NUM_SENSORS; i += 3) {
        leds[i / 3] = CRGB(receivedBytes[i], receivedBytes[i + 1], receivedBytes[i + 2]);
      }
      
      FastLED.show();
      ledThisLoop = false;
      newData = false;
    } 
  }
  else {
    unsigned long now = millis();

    scanAndDebounceSensors(now);

    recvCommand();

    if (newData) {
      handleCommand(receivedChars);
      newData = false;
    }
  }

}

void recvBytesWithStartEndMarkers() {
  static boolean recvInProgress = false;
  static byte ndx = 0;
  const byte startMarker = 0xFE;
  const byte endMarker = 0xFF;
  byte rb;

  while (Serial.available() > 0 && newData == false) {
    rb = Serial.read();

    if (recvInProgress) {
      if (rb != endMarker) {
        receivedBytes[ndx++] = rb;
        if (ndx >= numBytes) ndx = numBytes; // just clip to max
      } else {
        // End of frame
        recvInProgress = false;
        numReceived = ndx;   // correct count of actual bytes
        ndx = 0;
        newData = true;
      }
    } else if (rb == startMarker) {
      recvInProgress = true;
      ndx = 0; // reset buffer start on every new packet
    }
  }
}




void handleCommand(const char* cmd) {
  // Check if it's a param command (e.g. threshold:600)
  char* colon = strchr(cmd, ':');
  if (colon) {
    *colon = '\0';                  // Split string at colon
    const char* key = cmd;          // Left part
    const char* valueStr = colon + 1; // Right part
    int value = atoi(valueStr);
    handleParamCommand(key, value);
    return;
  }

  // Otherwise, handle regular command
  for (Command& c : commands) {
    if (strcmp(cmd, c.name) == 0) {
      c.func();
      return;
    }
  }
}

void handleParamCommand(const char* key, int value) {
  if (strcmp(key, "sensitivity") == 0) {
    sensitivity = value;
  }
  if (strcmp(key, "south_thresh") == 0) {
    south_thresh = value;
  }
  if (strcmp(key, "north_thresh") == 0) {
    north_thresh = value;
  }
  // Add more param-based commands as needed
}

void prepForLed() {
  ledThisLoop = true;
  sendData("awaiting");
}

void scanAndDebounceSensors(unsigned long now) {
  for (int i = 0; i < NUM_SENSORS; i++) {
    char raw = getRawState(i);
    updateDebounce(i, raw, now);
  }
}

void sendCurrentSensitivity() {
  sendData(String(sensitivity));
}

void sendCurrentnorth_thresh() {
  sendData(String(north_thresh));
}

void sendCurrentsouth_thresh() {
  sendData(String(south_thresh));
}

void sendAverage() {
  sendData(String(averageReading));
}

int readMux(int index) {
  int muxIdx = index / 16;
  int channel = index % 16;

  for (int i = 0; i < 4; i++) digitalWrite(enPins[i], HIGH);
  digitalWrite(enPins[muxIdx], LOW);
  mux.channel(channel);

  // Simple 4-sample average
  int sum = 0;
  for (int i = 0; i < readingsperreading; i++) sum += analogRead(SIGNAL_PIN);
  return sum / readingsperreading;
}

int average(int *arr, int len) {
  long sum = 0;
  for (int i = 0; i < len; i++) sum += arr[i];
  return sum / len;
}

char getRawState(int i) {
  static char lastState[NUM_SENSORS]; // store last returned state

  int val = readMux(i);

  if (val > averageReading + (north_thresh)) {
    lastState[i] = 'n';
  } 
  else if (val < averageReading - (south_thresh)) {
    lastState[i] = 's';
  } 
  else {
    lastState[i] = 'z';
  }
  // else keep last state
  return lastState[i];
}

void updateDebounce(int i, char raw, unsigned long now) {
  if (raw != lastRawStates[i]) {
    lastRawStates[i] = raw;
    lastChangeTime[i] = now;
  }

  if ((now - lastChangeTime[i]) > DEBOUNCE_MS) {
    stableStates[i] = raw;
  }
}

void sendStates() {
  Serial.print(START_CHAR);
  for (int i = 0; i < NUM_SENSORS; i++) {
    Serial.print(stableStates[i]);
  }
  Serial.print(END_CHAR);
}

void sendData(String data) {
  Serial.print(START_CHAR);
  Serial.print(data);
  Serial.print(END_CHAR);
}

void recvCommand() {
  static bool inProgress = false;
  static byte ndx = 0;
  char rc;

  while (Serial.available() && !newData) {
    rc = Serial.read();

    if (inProgress) {
      if (rc != END_CHAR) {
        if (ndx < CMD_BUFFER - 1) {
          receivedChars[ndx++] = rc;
        }
      } else {
        receivedChars[ndx] = '\0';
        inProgress = false;
        ndx = 0;
        newData = true;
      }
    } else if (rc == START_CHAR) {
      inProgress = true;
    }
  }
}

void calibrateSensors() {
  int readingsOn[NUM_SENSORS];
  int readingsOff[NUM_SENSORS];

  // --- Lights OFF reading ---
  fill_solid(leds, NUM_SENSORS, CRGB::Black);
  FastLED.show();
  delay(100); // wait for LEDs to turn off

  for (int i = 0; i < NUM_SENSORS; i++) {
    readingsOff[i] = readMux(i);
  }

  // --- Lights ON reading ---
  fill_solid(leds, NUM_SENSORS, CRGB::White);
  FastLED.show();
  delay(100); // wait for LEDs to turn on

  for (int i = 0; i < NUM_SENSORS; i++) {
    readingsOn[i] = readMux(i);
  }

  // --- Average lights off and on readings ---
  int readingsAvg[NUM_SENSORS];
  for (int i = 0; i < NUM_SENSORS; i++) {
    readingsAvg[i] = (readingsOff[i] + readingsOn[i]) / 2;
  }

  averageReading = average(readingsAvg, NUM_SENSORS);

  // averageReading = 238;

  // Turn LEDs off after calibration
  fill_solid(leds, NUM_SENSORS, CRGB::Black);
  FastLED.show();
  
  Serial.print("<ready>");
}
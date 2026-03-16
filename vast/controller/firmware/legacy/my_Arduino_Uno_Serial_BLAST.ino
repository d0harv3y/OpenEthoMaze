/****************************************************************************************	
**  This is example LINX firmware for use with the Arduino Uno with the serial 
**  interface enabled.
**
**  For more information see:           www.labviewmakerhub.com/linx
**  For support visit the forums at:    www.labviewmakerhub.com/forums/linx
**  
**  Written By Sam Kristoff
**
**  BSD2 License.
****************************************************************************************/

//Include All Peripheral Libraries Used By LINX
#include <SPI.h>
#include <Wire.h>
#include <EEPROM.h>
#include <Servo.h>

//Include Device Specific Header From Sketch>>Import Library (In This Case LinxChipkitMax32.h)
//Also Include Desired LINX Listener From Sketch>>Import Library (In This Case LinxSerialListener.h)
#include <LinxArduinoUno.h>
#include <LinxSerialListener.h>

//custom
#include <DmxSimple.h>
 
//Create A Pointer To The LINX Device Object We Instantiate In Setup()
LinxArduinoUno* LinxDevice;
int myCustomDMXCommand();
int myCustomToneCommand();
int soundPin = 7;
int startBUTNpin = 4;
int LEDpin = 13;

//Initialize LINX Device And Listener
void setup()
{
  //Instantiate The LINX Device
  LinxDevice = new LinxArduinoUno();
  
  //The LINXT Listener Is Pre Instantiated, Call Start And Pass A Pointer To The LINX Device And The UART Channel To Listen On
  LinxSerialConnection.Start(LinxDevice, 0);  
  
  pinMode(soundPin, OUTPUT);    
  pinMode(LEDpin, OUTPUT);    
  pinMode(startBUTNpin, INPUT);   
  //attatch custom
  LinxSerialConnection.AttachCustomCommand(1, myCustomDMXCommand);
  DmxSimple.usePin(LEDpin);
  //DmxSimple.maxChannel(4);
  LinxSerialConnection.AttachCustomCommand(0, myCustomToneCommand);
    //digitalWrite(soundPin,HIGH);
    //delayMicroseconds(50);
    //digitalWrite(soundPin,LOW);
}

void loop()
{
  //Listen For New Packets From LabVIEW
  LinxSerialConnection.CheckForCommands();
  
  //Your Code Here, But It will Slow Down The Connection With LabVIEW
}

//custom
int myCustomDMXCommand(unsigned char numInputBytes, unsigned char* input, unsigned char* numResponseBytes, unsigned char* response)
{
	for(int i=0; i<numInputBytes; i++)
	{
		DmxSimple.write(i+1,input[i]);
	}
	return 0;
}
int myCustomToneCommand(unsigned char numInputBytes, unsigned char* input, unsigned char* numResponseBytes, unsigned char* response)
{
  int d=50;
 DmxSimple.pause();
  for(int i=0; i<(1000000/d/2); i++)
  {
    digitalWrite(soundPin,HIGH);
    delayMicroseconds(d);
    digitalWrite(soundPin,LOW);
    delayMicroseconds(d);
  }
 DmxSimple.resume();
  return 0;
}

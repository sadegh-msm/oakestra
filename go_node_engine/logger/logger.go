package logger

import (
	"fmt"
	"log"
	"os"
	"sync"
	"time"
)

var infologger *log.Logger
var errorlogger *log.Logger
var filelogger *log.Logger
var infoonce sync.Once
var erroronce sync.Once
var fileonce sync.Once

type EventType string

const (
	DEPLOYREQUEST   EventType = "DEPLOY_REQUEST"
	UNDEPLOYREQUEST EventType = "UNDEPLOY_REQUEST"
	DEPLOYED        EventType = "DEPLOYED"
	DEAD            EventType = "DEAD"
)

func InfoLogger() *log.Logger {
	infoonce.Do(func() {
		infologger = log.New(os.Stdout, "INFO-", log.Ldate|log.Ltime|log.Lshortfile)
	})
	return infologger
}

func ErrorLogger() *log.Logger {
	erroronce.Do(func() {
		errorlogger = log.New(os.Stderr, "ERROR-", log.Ldate|log.Ltime|log.Lshortfile)
	})
	return errorlogger
}

func CsvLog(event EventType, sname string, content string) {
	fileonce.Do(func() {
		filelog, err := os.OpenFile("eventLogger.csv", os.O_RDWR|os.O_CREATE|os.O_APPEND, 0666)
		if err != nil {
			log.Fatalf("error opening file: %v", err)
		}
		filelogger = log.New(filelog, "", 0)
	})
	filelogger.Printf("%d;%s;%s;%s;\n", time.Now().UnixMilli(), sname, event, fmt.Sprintf("{log:\"%s\"}", content))
}

func GetServiceLogfile(sname string) *os.File {
	logfile, err := os.OpenFile(fmt.Sprintf("logfile-%s.log", sname), os.O_RDWR|os.O_CREATE|os.O_APPEND, 0666)
	if err != nil {
		log.Fatalf("error opening file: %v", err)
	}
	return logfile
}

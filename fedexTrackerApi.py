import time
import requests 
import json 

#store all the crucial pieces from api into simple details object
class DeliveryDetails:
  #this is the constructor to bring all the different attributes under one object 
  def __init__(self, tracking, deliveryStatus, shippedDate, deliveryDate,deliveryTime, returnDetails, alternateTrackingNbr,returnReason, returnToSenderDate,  returnedDate  ):
    self.tracking = tracking
    self.deliveryStatus = deliveryStatus
    self.shippedDate = shippedDate
    self.deliveryDate = deliveryDate
    self.deliveryTime = deliveryTime
    self.returnDetails = returnDetails
    self.alternateTrackingNbr = alternateTrackingNbr
    self.returnReason = returnReason
    self.returnToSenderDate  = returnToSenderDate  
    self.returnedDate = returnedDate 


#get the fedex token - need to provide api key and secret for fedex
def GetFedExToken( session ): 

    #this needs to be replaced with api key and secret
    apikey_client_id = "PUT API KEY HERE"
    secret = "PUT API SECRET HERE"
    payloadLogin = { "client_id": apikey_client_id, "client_secret": secret, "grant_type":"client_credentials" }
 
    url = "https://apis.fedex.com/oauth/token"
    payloadLogin = session.post(url, data=payloadLogin) 
 
    #the api will give a token that can be used for future calls
    tokenLogin =  json.loads( payloadLogin.text)
    bearerToken = 'Bearer ' + tokenLogin['access_token']

    #header of future calls needs to have the bearer token
    header = { 
        "Authorization":bearerToken,
        "content-type": "application/json"
    }
    
    return header

#api only needs the tracking number passed
def CallFedExTrackingApi( session, headerAndToken, trackingnumber ):
      
    #return the fedex tracking details. 
    body = {
      "trackingInfo": [
        {
          "trackingNumberInfo": {
            "trackingNumber": trackingnumber
          }
        }
      ],
      "includeDetailedScans":  "true"
    }
 
    #fedex production api for tracking package deliveries 
    url = "https://apis.fedex.com/track/v1/trackingnumbers"
    response = session.post(url, headers=headerAndToken,data=json.dumps(body) )
    
    #if token has expired regnerate it
    if not response.ok:
        headerAndToken = GetFedExToken( session );
        response = session.post(url, headers=headerAndToken,data=json.dumps(body) )

    #response text is json so use python json library to parse it
    jsonResposne = json.loads( response.text)

    #since we're only tracking one number at a time, we can reference the 0th element
    trackDetails = jsonResposne['output']['completeTrackResults'][0]['trackResults'][0]

    return trackDetails



#fedex quota rules: https://developer.fedex.com/api/en-us/guides/ratelimits.html

#fedex object returned needs to be parsed so the key details can be extracted
def FedExDeliveryObjectParser( headerToken, track, session, trackingNumber):
    d = DeliveryDetails("",'',None,None,None,'','','',None,None) # += None and str throws exception
    
    d.tracking = track
    scanEvents = track["scanEvents"]
    returnTracker = track['additionalTrackingInfo']['packageIdentifiers']
    lastResults = track['latestStatusDetail']

    #only try to grab the evens if the package has been delivered
    d.deliveryDate = scanEvents[ 0 ]["date"][0:19] if scanEvents[ 0 ]["eventDescription"] == 'Delivered' else ''
    #the event before the last should be the ship date 
    d.shippedDate = scanEvents[ len(scanEvents) - 1 ]["date"]
    d.shippedDate = d.shippedDate[0:19]
    d.deliveryStatus = lastResults["description"] 

    #the return section can have multiple events
    for returnPart in returnTracker:
        #the return section that has the return tracking number is under this named type
        if returnPart["type"] == "RETURNED_TO_SHIPPER_TRACKING_NUMBER":
            d.alternateTrackingNbr = returnPart["values"][0] 

            #the return tracking number has the return date 
            returnTracking = CallFedExTrackingApi( session, headerToken, d.alternateTrackingNbr)
            returnScans = returnTracking["scanEvents"]

            #if the package has been returned we can get the return date 
            if len( returnScans  ) > 0: 
                d.returnToSenderDate = returnScans[0]["date"][0:19]
 

    #this only exists if the packaged wasn't delivered - 
    if lastResults["description"] == "Delivery exception":
        #here we can try to get why the pacakge was returned 
        if len( lastResults["ancillaryDetails"])  > 0 and lastResults["ancillaryDetails"][0]["action"] == "No action is required.  The package is being returned to the shipper.":
            for scan in scanEvents: 
                #multiple junk events exsists, we just want to get why the package was returned 
                if scan["exceptionCode"] != "" and scan["exceptionDescription"] != "Package delayed":
                    d.returnReason += scan["exceptionDescription"] + ". "
                    #when the packages is sent to be returned
                    d.returnedDate = scan["date"][0:19]
    return d

#basic structure to get details of fedex tracking number
if __name__ == "__main__":

    #trackingnumber = "563857546141" #return
    trackingnumber = "551530747590" #delivered

    #create new web session
    session = requests.sessions.Session()    

    #get the fedex token so we can use their api
    headerToken = GetFedExToken(session)
     
    #call the api for tracking a package
    trackResponse = CallFedExTrackingApi(session, headerToken, trackingnumber)

    #parse the details of the api into a more useful object. 
    myDetails = FedExDeliveryObjectParser( headerToken, trackResponse, session, trackingnumber)
 
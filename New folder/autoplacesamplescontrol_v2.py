###############################################
##SCRIPT BY  :  Ang Shimin
##CREATED    :  25 Aug 2014
##INPUT      :
##DESCRIPTION : This code retrieves attributes of samples, working solutions and controls from the server, triplicates them and
##              determines the new well plate positions ignoring their original postion. Triplicated working solutions and
##              controls are place in the first 3 rows and in a downwards fashion. Artifacts are also placed in a similar fashion.
##				v2.3.1 getContainer uses xml attributes
##VERSION    :  2.3.1
###############################################
import sys
import getopt
import xml.dom.minidom
import glsapiutil
from xml.dom.minidom import parseString

HOSTNAME = 'http://dlap73v.gis.a-star.edu.sg:8080'
##HOSTNAME = 'http://192.168.8.10:8080'
VERSION = "v2"
BASE_URI = HOSTNAME + "/api/" + VERSION + "/"

DEBUG = False
api = None

ARTIFACTS = {}
CACHE_IDS = []
I2OMap = {} # A mapping of inputs to their outputs
POSITIONS = [ 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H' ]

placeFlag = 0
wellArr = []
rowNum = 0
sampleCount = 0
letterVal = 65

def getStepConfiguration( ):

        response = ""

        if len( args[ "stepURI" ] ) > 0:
                stepXML = api.getResourceByURI( args[ "stepURI" ] )
                stepDOM = parseString( stepXML )
                nodes = stepDOM.getElementsByTagName( "configuration" )
                if nodes:
                        response = nodes[0].toxml()

        return response

def cacheArtifact( limsid ):

        global CACHE_IDS

        if limsid not in CACHE_IDS:
                CACHE_IDS.append( limsid )

def prepareCache():

        global ARTIFACTS

        lXML = '<ri:links xmlns:ri="http://genologics.com/ri">'

        for limsid in CACHE_IDS:
                link = '<link uri="' + BASE_URI + 'artifacts/' + limsid + '" rel="artifacts"/>'
                lXML += link
        lXML += '</ri:links>'

        mXML = api.getBatchResourceByURI( BASE_URI + "artifacts/batch/retrieve", lXML )
        mDOM = parseString( mXML )
        nodes = mDOM.getElementsByTagName( "art:artifact" )
        for artifact in nodes:
                aLUID = artifact.getAttribute( "limsid" )
                ARTIFACTS[ aLUID ] = artifact

def getArtifact( limsid ):

        response = ARTIFACTS[ limsid ]
        return response

def getContainer( limsid ):
        response = ""

        gURI = BASE_URI + "containers/" + limsid
        gXML = api.getResourceByURI( gURI )
        gDOM = parseString( gXML )

        Nodes = gDOM.getElementsByTagName("con:container")
        if(Nodes):
                temp = Nodes[0].getElementsByTagName("type")
                response = temp[0].getAttribute("name")

        return response

def createContainer( type, name ):

        response = ""

        if type == '96':
                cType = '1'
                cTypeName = "96 well plate"
        elif type == '384':
                cType = '3'
                cTypeName = "384 well plate"

        xml ='<?xml version="1.0" encoding="UTF-8"?>'
        xml += '<con:container xmlns:con="http://genologics.com/ri/container">'
        xml += '<name>' + name + '</name>'
        xml += '<type uri="' + BASE_URI + 'containertypes/' + cType + '" name="' + cTypeName + '"/>'
        xml += '</con:container>'

        response = api.createObject( xml, BASE_URI + "containers" )

        rDOM = parseString( response )
        Nodes = rDOM.getElementsByTagName( "con:container" )
        if Nodes:
                temp = Nodes[0].getAttribute( "limsid" )
                response = temp
        return response

def getNewWP( iWP, replicateType, replicateNumber, noOfWS, containerName ):

        global placeFlag
        global rowNum
        global wellArr
        global sampleCount
        global letterVal

        pos = 1
        temp = 0
        rowsInContainer = 0

        if(containerName == "96 well plate"):   #decides when to shift col due to end of rows
                rowsInContainer = 8
        else:
                rowsInContainer = 16

        if(placeFlag == 0):             #if its the first sample, set everything to default
                letterVal = 65
                placeFlag = 1
                sampleCount = 0
                rowNum = 0
                wsOffset = 3

#               if(noOfWS < 1):
#                       wsOffset = 0 * replicateNumber
#               else:
#                       wsOffset = 1 * replicateNumber

                for n in range (0, replicateNumber):            #replicateNumber determines arr length, each element if wsOffset plus index+1
                        wellArr.insert(n, wsOffset+pos)
                        print(str(wellArr[n]))
                        pos = pos + 1

        else:
                sampleCount = sampleCount + 1
                temp2 = sampleCount % (rowsInContainer*replicateNumber)       #there is 24 samples, including the triplicates in 3 cols, A - H
                if(not temp2 == 0):             #if between row A to H on 96 well plate

                        temp = sampleCount % replicateNumber            #only change row for every 3rd sample
                        if(temp == 0):
                                letterVal = letterVal + 1       #increase to next row
                                rowNum = rowNum + 1


                elif(temp2 == 0):
                        for i  in range (0, replicateNumber):
                                wellArr[i] = wellArr[i] + replicateNumber     ## shift to offset replications
                                rowNum = 0
                                letterVal = 65                  #reset letter back to A but shift to next 3 cols


        response = chr(letterVal) + ":" + str(wellArr[replicateType-1])
        print(response)
        return response

def getWS_WP( name, replicateNumber ):

        tokens = name.split( "-" )
        temp = tokens[1].strip()
        number = int( temp[0] )

        alpha = POSITIONS[ number ]
        WP = alpha + ":" + str(replicateNumber)

        return WP

def getWSCount():
        count = 0
        for key in I2OMap:
                outs = I2OMap[ key ]

                for output in outs:
                        oDOM = getArtifact( output )
                        Nodes = oDOM.getElementsByTagName( "name" )
                        oName = api.getInnerXml( Nodes[0].toxml(), "name" )
                        if DEBUG: print oName

                        WP = ""

                        if oName.find( "_1" ) > -1: replicateNumber = 1
                        elif oName.find( "_2" ) > -1: replicateNumber = 2
                        elif oName.find( "_3" ) > -1: replicateNumber = 3

                        ## are we dealing with control samples?
                        if oName.find( "Working Solution" ) > -1:
                                count =+ 1
        return count

def autoPlace():

        global I2OMap
        wsCountNum = 0

        containerType = createContainer( '96', '96 WP' )
        containerName = getContainer(containerType)

        ## step one: get the process XML
        pURI = BASE_URI + "processes/" + args[ "limsid" ]
        pXML = api.getResourceByURI( pURI )
        pDOM = parseString( pXML )

        IOMaps = pDOM.getElementsByTagName( "input-output-map" )

        for IOMap in IOMaps:

                output = IOMap.getElementsByTagName( "output" )
                oType = output[0].getAttribute( "output-type" )
                ogType = output[0].getAttribute( "output-generation-type" )
                ## switch these lines depending upon whether you are placing ResultFile measurements, or real Analytes
                ##if oType == "Analyte":
                if oType == "ResultFile" and ogType == "PerInput":

                        limsid = output[0].getAttribute( "limsid" )
                        cacheArtifact( limsid )
                        nodes = IOMap.getElementsByTagName( "input" )
                        iLimsid = nodes[0].getAttribute( "limsid" )
                        cacheArtifact( iLimsid )

                        ## create a map entry
                        if not iLimsid in I2OMap.keys():
                                I2OMap[ iLimsid ] = []
                        temp = I2OMap[ iLimsid ]
                        temp.append( limsid )
                        I2OMap[ iLimsid ] = temp

        ## the placement logic requires the samples be uniformly duplicate or tripicate
        ## let's verify and head for the showers if it's not
        counts = []
        for key in I2OMap:
                temp = len(I2OMap[ key ])
                if temp not in counts:
                        counts.append( temp )

        ## if counts contains more than 1 value we have a problem
        if len(counts) > 1:
                msg = "The script is expecting the samples to be homogenously duplicate or triplicate, you have a heterogeneus mixture of replicates"
                api.reportScriptStatus( args[ "stepURI" ], "ERROR", msg )
        else:

                ## build our cache of Analytes
                prepareCache()

                pXML = '<?xml version="1.0" encoding="UTF-8"?>'
                pXML += ( '<stp:placements xmlns:stp="http://genologics.com/ri/step" uri="' + args[ "stepURI" ] +  '/placements">' )
                pXML += ( '<step uri="' + args[ "stepURI" ] + '"/>' )
                pXML += getStepConfiguration()
                pXML += '<selected-containers>'
                pXML += ( '<container uri="' + BASE_URI + 'containers/' + containerType + '"/>' )
                pXML += '</selected-containers><output-placements>'

                highestControlPosition = ""
                noOfWS = getWSCount()

                ## let's process our cache, one input at a time, but ignore some control samples
                for key in I2OMap:

                        ## get the well position for the input
                        iDOM = getArtifact( key )
                        nodes = iDOM.getElementsByTagName( "value" )
                        iWP = api.getInnerXml( nodes[0].toxml(), "value" )
                        ## well placement should always contain a :
                        if iWP.find( ":" ) == -1:
                                print( "WARN: Unable to determine well placement for artifact " + key )
                                break

                        outs = I2OMap[ key ]
                        if DEBUG: print( key + str(outs) )
                        for output in outs:
                                oDOM = getArtifact( output )
                                oURI = oDOM.getAttribute( "uri" )
                                Nodes = oDOM.getElementsByTagName( "name" )
                                oName = api.getInnerXml( Nodes[0].toxml(), "name" )
                                if DEBUG: print oName

                                WP = ""

                                if oName.find( "_1" ) > -1: replicateNumber = 1
                                elif oName.find( "_2" ) > -1: replicateNumber = 2
                                elif oName.find( "_3" ) > -1: replicateNumber = 3

                                ## are we dealing with control samples?
                                if oName.find( "Working Solution" ) > -1:
                                        WP = getWS_WP( oName, replicateNumber )
                                        alpha = WP[0]
                                        if alpha > highestControlPosition:
                                                highestControlPosition = alpha
                                elif oName.find( "Positive Control" ) > -1:
                                        continue
                                else:
                                        WP = getNewWP( iWP, replicateNumber, counts[0], noOfWS, containerName )

                                if DEBUG: print( oName, WP )

                                if WP != "":
                                        plXML = '<output-placement uri="' + oURI + '">'
                                        plXML += ( '<location><container uri="' + BASE_URI + 'containers/' + containerType + '" limsid="' + containerType + '"/>' )
                                        plXML += ( '<value>' + WP + '</value></location></output-placement>' )

                                        pXML += plXML

                ## now deal with those pesky controls that MUST be placed last
                for key in I2OMap:

                        ## get the well position for the input
                        iDOM = getArtifact( key )
                        nodes = iDOM.getElementsByTagName( "value" )
                        iWP = api.getInnerXml( nodes[0].toxml(), "value" )

                        outs = I2OMap[ key ]
                        for output in outs:
                                oDOM = getArtifact( output )
                                oURI = oDOM.getAttribute( "uri" )
                                Nodes = oDOM.getElementsByTagName( "name" )
                                oName = api.getInnerXml( Nodes[0].toxml(), "name" )

                                WP = ""

                                if oName.find( "_1" ) > -1: replicateNumber = 1
                                elif oName.find( "_2" ) > -1: replicateNumber = 2
                                elif oName.find( "_3" ) > -1: replicateNumber = 3

                                ## are we dealing with control samples?
                                if oName.find( "Positive Control" ) > -1:
                                        for i in range( 0, len(POSITIONS) ):
                                                posCount = i
                                                if POSITIONS[ i ] == highestControlPosition:
                                                        break
                                        alpha = POSITIONS[ posCount + 1 ]
                                        WP = alpha + ":" + str( replicateNumber )
                                else:
                                        continue

                                if DEBUG: print( oName, WP )

                                if WP != "":
                                        plXML = '<output-placement uri="' + oURI + '">'
                                        plXML += ( '<location><container uri="' + BASE_URI + 'containers/' + containerType + '" limsid="' + containerType + '"/>' )
                                        plXML += ( '<value>' + WP + '</value></location></output-placement>' )

                                        pXML += plXML

                pXML += '</output-placements></stp:placements>'

                rXML = api.createObject( pXML, args[ "stepURI" ] + "/placements" )
                rDOM = parseString( rXML )
                nodes = rDOM.getElementsByTagName( "output-placement" )
                if nodes:
                        msg = "Auto-placement of replicates occurred successfully"
                        api.reportScriptStatus( args[ "stepURI" ], "OK", msg )
                else:
                        msg = "An error occurred trying to auto-place these replicates"
                        msg = msg + rXML
                        print msg
                        api.reportScriptStatus( args[ "stepURI" ], "WARN", msg )

def main():

        global api
        global args

        args = {}

        opts, extraparams = getopt.getopt(sys.argv[1:], "l:u:p:s:")

        for o,p in opts:
                if o == '-l':
                        args[ "limsid" ] = p
                elif o == '-u':
                        args[ "username" ] = p
                elif o == '-p':
                        args[ "password" ] = p
                elif o == '-s':
                        args[ "stepURI" ] = p

        api = glsapiutil.glsapiutil()
        api.setHostname( HOSTNAME )
        api.setVersion( VERSION )
        api.setup( args[ "username" ], args[ "password" ] )

        ## at this point, we have the parameters the EPP plugin passed, and we have network plumbing
        ## so let's get this show on the road!

        autoPlace()

if __name__ == "__main__":
        main()



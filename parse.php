<?php

declare(strict_types=1);

ini_set('display_errors', 'stderr');

class EXITCODE
{
    public static $OK = 0;
    public static $ERR_ARGS = 10;
    public static $ERR_HEADER = 21;
    public static $ERR_OTHER = 23;
    public static $ERR_OP_CODE = 22;
}

//IPPcode 23 language description

//instruction argument list
$INS_ARG_LIST = array(
    "MOVE" => ['Var', 'Symb'],
    "STRLEN" => ['Var', 'Symb'],
    "TYPE" => ['Var', 'Symb'],
    "DEFVAR" => ['Var'],
    "POPS" => ['Var'],
    "CALL" => ['Label'],
    "LABEL" => ['Label'],
    "JUMP" => ['Label'],
    "PUSHS" => ['Symb'],
    "WRITE" => ['Symb'],
    "EXIT" => ['Symb'],
    "DPRINT" => ['Symb'],
    "ADD" => ['Var', 'Symb', 'Symb'],
    "SUB" => ['Var', 'Symb', 'Symb'],
    "MUL" => ['Var', 'Symb', 'Symb'],
    "IDIV" => ['Var', 'Symb', 'Symb'],
    "LT" => ['Var', 'Symb', 'Symb'],
    "GT" => ['Var', 'Symb', 'Symb'],
    "EQ" => ['Var', 'Symb', 'Symb'],
    "AND" => ['Var', 'Symb', 'Symb'],
    "OR" => ['Var', 'Symb', 'Symb'],
    "NOT" => ['Var', 'Symb', 'SymbOpt'],
    "INT2CHAR" => ['Var', 'Symb'],
    "CONCAT" => ['Var', 'Symb', 'Symb'],
    "STRI2INT" => ['Var', 'Symb', 'Symb'],
    "GETCHAR" => ['Var', 'Symb', 'Symb'],
    "SETCHAR" => ['Var', 'Symb', 'Symb'],
    "READ" => [
        'Var',
        'Type',
    ],
    "JUMPIFEQ" => ['Label', 'Symb', 'Symb'],
    "JUMPIFNEQ" => ['Label', 'Symb', 'Symb'],
    "CREATEFRAME" => [],
    "PUSHFRAME" => [],
    "POPFRAME" => [],
    "RETURN" => [],
    "BREAK" => [],
);

//patterns for regex parsing
$PATTERN_HEADER = "^(?i)\.IPPcode23$";
$PATTERN_VAR_NAME = "[a-zA-Z_$&%*!?-]+[a-zA-Z0-9_$&%*!?-]*";
$PATTERN_VAR = "^" . "(GF|LF|TF)@" . $PATTERN_VAR_NAME . "$";
$PATTERN_CONST_INT = "int@(\\+|-)?((?i)[0-9]+|0x[0-9a-f]+)";
$PATTERN_CONST_NIL = "^nil@nil$";
$PATTERN_CONST_STRING = "string@*+";
$PATTERN_CONST_BOOL = "bool@(true|false)";
$PATTERN_LIT_NOT_STRING = "^(" . $PATTERN_CONST_INT . "|" . $PATTERN_CONST_NIL . "|" . $PATTERN_CONST_BOOL . ")$";
$PATTERN_CONST = "(" . $PATTERN_CONST_INT . "|" . $PATTERN_CONST_STRING . "|" . $PATTERN_CONST_NIL . "|" . $PATTERN_CONST_BOOL . ")";
$PATTERN_SYMB = "(" . $PATTERN_CONST . "|" . $PATTERN_VAR . ")";
$PATTERN_TYPE = "^(int|string|bool)$";
$PATTERN_LABEL = "^" . $PATTERN_VAR_NAME . "$";
//-------------------------
function createRegex($str)
{
    return "/" . $str . "/";
}
//-----------------------
function errorExit($msg, $code)
{
    fwrite(STDERR, "ERROR: " . $msg . "\n");
    exit($code);
}

function printHelp()
{
    echo ("Usage: php8.1 parse.php <HELP>\n");
    echo ("  This script reads code written in IPP23 from stdin and writes formatted XML document to stdout.\n");
    echo ("    <HELP> : '--help' : optional parameter, prints this message.\n");
}

function handleArgs()
{
    global $argc, $argv;
    if ($argc == 2) {
        if ($argv[1] == "--help") {
            printHelp();
            exit(EXITCODE::$OK);
        } else {
            printHelp();
            errorExit("incorrect arguments", EXITCODE::$ERR_ARGS);
        }
    } else if ($argc > 2) {
        printHelp();
        errorExit("incorrect arguments", EXITCODE::$ERR_ARGS);
    }
}


class WriterXML
{
    private SimpleXMLElement $xmlOut, $insXML; //insXML is current instruction xml, xmlOut is root xml object
    private int $insIndex, $argIndex; //argIndex counts args per instruction, insIndex count instruction per program

    public function init()
    {
        //initialize outupt xml
        $xmlStr = <<<XML
        <?xml version="1.0" encoding="UTF-8"?>
        <program language="IPPcode23">
        </program>
        XML;
        $this->xmlOut = new SimpleXMLElement($xmlStr);
        $this->insIndex = 1;
        $this->argIndex = 1;
    }

    public function addInstruction($opcodeStr)
    {
        //genereta instruction xml
        $this->insXML = $this->xmlOut->addChild("instruction");
        $this->insXML->addAttribute("order", strval($this->insIndex));
        $this->insXML->addAttribute("opcode", $opcodeStr);
        $this->insIndex++;
        $this->argIndex = 1;
    }

    public function addArgument($inner, $type)
    {
        //generate argument xml for current instruction
        $argXML = $this->insXML->addChild("arg$this->argIndex", $inner);
        $argXML->addAttribute("type", $type);
        $this->argIndex++;
    }

    public function print()
    {
        echo $this->xmlOut->asXML();
    }
}

class Parser
{
    private WriterXML $writer;

    function __construct()
    {
        $this->writer = new WriterXML();
    }

    function lineCutoffCommentAndTrim($line)
    {
        $linePieces = explode("#", $line);
        if (count($linePieces) > 1)
            $line = $linePieces[0]; //cut off comment
        $line = trim($line);
        return $line;
    }

    private function checkHeader()
    {
        global $PATTERN_HEADER;
        $found_header = false;
        while ($line = fgets(STDIN)) {
            $line = $this->lineCutoffCommentAndTrim($line);
            if ($line == "") //line is empty, skip
                continue;
            else if (preg_match(createRegex($PATTERN_HEADER), $line) == 1) {
                $found_header = true;
                return;
            } else { //line is not header
                errorExit("invalid header", EXITCODE::$ERR_HEADER);
            }
        }
        if ($found_header == false) {
            errorExit("invalid header", EXITCODE::$ERR_HEADER);
        }
    }

    function checkArgVar($wordStr)
    {
        //check var
        global $PATTERN_VAR;
        if (preg_match(createRegex($PATTERN_VAR), $wordStr) != 1) {
            errorExit("invalid <Var>: " . $wordStr, EXITCODE::$ERR_OTHER);
        }
        //generete arg
        $this->writer->addArgument(htmlspecialchars($wordStr), "var");
    }

    function checkArgSymbOpt($wordStr)
    {
        //optional symb argument check
        if ($wordStr != "") {
            $this->checkArgSymb($wordStr);
        }
    }

    function checkArgSymb($wordStr)
    {
        //check legality of a string literal
        $isStringLiteralLegal = function ($str) {
            $a = preg_match_all("/\\\/", $str);
            $b = preg_match_all("/\\\[0-9]{3}/", $str);
            if ($a == $b)
                return true;
            return false;
        };
        global $PATTERN_SYMB;
        global $PATTERN_VAR;
        global $PATTERN_LIT_NOT_STRING;
        global $PATTERN_CONST_STRING;
        $typeStr = "";
        $valueStr = "";
        //check symbol type
        if (preg_match(createRegex($PATTERN_VAR), $wordStr) == 1) { //variable
            $typeStr = "var";
            $valueStr = "$wordStr";
        } else if (preg_match(createRegex($PATTERN_CONST_STRING), $wordStr) == 1) { //string literal
            $literalStr = explode("@", $wordStr)[1];
            $valueStr = htmlspecialchars($literalStr);
            if ($isStringLiteralLegal($valueStr) == false) {
                errorExit("invalid string literal: " . $valueStr, EXITCODE::$ERR_OTHER);
            }
            $typeStr = "string";
        } else if (preg_match(createRegex($PATTERN_LIT_NOT_STRING), $wordStr) == 1) { //other literal (bool, nil, int)
            //extract type and value
            $wordStrPieces = explode("@", $wordStr);
            $typeStr = $wordStrPieces[0];
            $valueStr = $wordStrPieces[1];
        } else { //error
            errorExit("invalid <Symb>: " . $wordStr, EXITCODE::$ERR_OTHER);
        }
        //generate xml
        $this->writer->addArgument($valueStr, $typeStr);
    }

    function checkArgLabel($wordStr)
    {
        //check
        global $PATTERN_LABEL;
        if (preg_match(createRegex($PATTERN_LABEL), $wordStr) != 1) {
            errorExit("invalid <label>", EXITCODE::$ERR_OTHER);
        }
        //generate xml
        $this->writer->addArgument($wordStr, "label");
    }

    function checkArgType($wordStr)
    {
        //check
        global $PATTERN_TYPE;
        if (preg_match(createRegex($PATTERN_TYPE), $wordStr) != 1) {
            errorExit("invalid <type>", EXITCODE::$ERR_OTHER);
        }
        //generate xml
        $this->writer->addArgument($wordStr, "type");
    }


    public function run()
    {
        //first check for header
        $this->checkHeader();

        //initialize writer
        $this->writer->init();

        //go through lines, skipping empty ones
        while ($line = fgets(STDIN)) {
            $line = $this->lineCutoffCommentAndTrim($line);
            if ($line == "")
                continue;

            //get opcode
            $wordStr = strtok($line, " ");
            $opcodeStr = strtoupper($wordStr);

            //generate xml instruction
            $this->writer->addInstruction($opcodeStr);

            global $INS_ARG_LIST;

            if (array_key_exists($opcodeStr, $INS_ARG_LIST)) {
                $argsStrArr = $INS_ARG_LIST[$opcodeStr];
            } else { //error, opcode not found
                errorExit("unknown opcode: " . $opcodeStr, EXITCODE::$ERR_OP_CODE);
            }

            //go through argument list
            foreach ($argsStrArr as $argStr) {
                $wordStr = strtok(" "); //get next word

                if ($wordStr == false) { //if no argument, send empty argument
                    $wordStr = "";
                } else {
                    $wordStr = trim($wordStr);
                }

                //get function name from argument name
                $argFunName = "checkArg" . $argStr;
                $this->$argFunName($wordStr);
            }

            if (strtok(" ") != false) { //found additional operands
                errorExit("additional operands", EXITCODE::$ERR_OTHER);
            }
        }

        //print final xml
        $this->writer->print();
    }
}

handleArgs();

$parser = new Parser();
$parser->run();
?>
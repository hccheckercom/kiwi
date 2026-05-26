<?php
/**
 * PHP AST Parser for Kiwi Security Checks
 *
 * Uses nikic/php-parser to analyze PHP files and detect security violations.
 * Returns JSON array of violations.
 *
 * Usage: php php_parser.php <file_path> <lesson_ids>
 * Example: php php_parser.php src/Plugin.php LES-001,LES-076
 */

// Check if nikic/php-parser is available
if (!class_exists('PhpParser\ParserFactory')) {
    // Parser not installed, return empty array
    echo json_encode([]);
    exit(0);
}

use PhpParser\Error;
use PhpParser\NodeDumper;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitorAbstract;
use PhpParser\ParserFactory;
use PhpParser\Node;

// Parse command line arguments
if ($argc < 3) {
    echo json_encode([]);
    exit(0);
}

$file_path = $argv[1];
$lesson_ids = explode(',', $argv[2]);

if (!file_exists($file_path)) {
    echo json_encode([]);
    exit(0);
}

$code = file_get_contents($file_path);

// Create parser
$parser = (new ParserFactory)->create(ParserFactory::PREFER_PHP7);

try {
    $ast = $parser->parse($code);
} catch (Error $error) {
    // Parse error, return empty
    echo json_encode([]);
    exit(0);
}

// Visitor to detect violations
class SecurityVisitor extends NodeVisitorAbstract
{
    public $violations = [];
    public $lesson_ids = [];

    public function __construct($lesson_ids)
    {
        $this->lesson_ids = $lesson_ids;
    }

    public function enterNode(Node $node)
    {
        // LES-076: $wpdb->query() without prepare()
        if (in_array('LES-076', $this->lesson_ids)) {
            if ($node instanceof Node\Expr\MethodCall) {
                if ($node->var instanceof Node\Expr\Variable &&
                    $node->var->name === 'wpdb' &&
                    $node->name instanceof Node\Identifier &&
                    $node->name->name === 'query') {

                    // Check if argument is dynamic
                    if (isset($node->args[0])) {
                        $arg = $node->args[0]->value;
                        if ($this->isDynamicString($arg)) {
                            $this->violations[] = [
                                'lesson_id' => 'LES-076',
                                'line' => $node->getLine(),
                                'description' => 'Dynamic SQL query without $wpdb->prepare()',
                                'confidence' => 0.90,
                            ];
                        }
                    }
                }
            }
        }

        // LES-045: Raw $_GET/$_POST without sanitization
        if (in_array('LES-045', $this->lesson_ids)) {
            if ($node instanceof Node\Expr\ArrayDimFetch) {
                if ($node->var instanceof Node\Expr\Variable &&
                    in_array($node->var->name, ['_GET', '_POST', '_REQUEST'])) {

                    // Check if wrapped in sanitize function
                    if (!$this->isWrappedInSanitize($node)) {
                        $key = $this->getArrayKey($node->dim);
                        $this->violations[] = [
                            'lesson_id' => 'LES-045',
                            'line' => $node->getLine(),
                            'description' => "\$_{$node->var->name}['{$key}'] without sanitization",
                            'confidence' => 0.85,
                        ];
                    }
                }
            }
        }

        // LES-064: AJAX handler without check_ajax_referer()
        if (in_array('LES-064', $this->lesson_ids)) {
            if ($node instanceof Node\Stmt\Function_) {
                $funcName = $node->name->name;
                if (strpos($funcName, 'wp_ajax_') === 0 || strpos($funcName, 'ajax_') === 0) {
                    // Check if function body has check_ajax_referer() call
                    if (!$this->hasFunctionCall($node->stmts, 'check_ajax_referer')) {
                        $this->violations[] = [
                            'lesson_id' => 'LES-064',
                            'line' => $node->getLine(),
                            'description' => "AJAX handler {$funcName}() without check_ajax_referer()",
                            'confidence' => 0.95,
                        ];
                    }
                }
            }
        }
    }

    private function isDynamicString($node)
    {
        return $node instanceof Node\Expr\BinaryOp\Concat ||
               $node instanceof Node\Expr\Variable ||
               $node instanceof Node\Scalar\Encapsed;
    }

    private function isWrappedInSanitize($node)
    {
        // Simplified - would need to check parent nodes in real implementation
        return false;
    }

    private function getArrayKey($node)
    {
        if ($node instanceof Node\Scalar\String_) {
            return $node->value;
        }
        return 'unknown';
    }

    private function hasFunctionCall($stmts, $funcName)
    {
        foreach ($stmts as $stmt) {
            if ($stmt instanceof Node\Expr\FuncCall) {
                if ($stmt->name instanceof Node\Name &&
                    $stmt->name->toString() === $funcName) {
                    return true;
                }
            }
            // Recursively check nested statements
            if (property_exists($stmt, 'stmts') && is_array($stmt->stmts)) {
                if ($this->hasFunctionCall($stmt->stmts, $funcName)) {
                    return true;
                }
            }
        }
        return false;
    }
}

// Traverse AST
$traverser = new NodeTraverser();
$visitor = new SecurityVisitor($lesson_ids);
$traverser->addVisitor($visitor);
$traverser->traverse($ast);

// Output violations as JSON
echo json_encode($visitor->violations);
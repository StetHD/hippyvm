from testing.test_interpreter import BaseTestInterpreter
import pytest

class TestPyPyBridge(BaseTestInterpreter):

    @pytest.fixture
    def php_space(self):
        return self.space

    def test_import_py_mod_func(self, php_space):
        output = self.run('''
            $math = import_py_mod("math");
            echo($math->pow(2, 3));
        ''')
        assert php_space.int_w(output[0]) == 8

    def test_import_py_mod_fails(self, php_space):
        output = self.run('''
            try {
                $m = import_py_mod("__ThIs_DoEs_NoT_ExIsT");
                echo "FAIL";
            } catch(PyException $e) {
                echo $e->getMessage();
            }
        ''')
        err_s = "No module named __ThIs_DoEs_NoT_ExIsT"
        assert php_space.str_w(output[0]) == err_s

    def test_import_py_mod_attr(self, php_space):
        import math
        output = self.run('''
            $math = import_py_mod("math");
            echo($math->pi);
        ''')
        assert php_space.float_w(output[0]) == math.pi

    def test_import_py_nested1_mod_func(self, php_space):
        output = self.run('''
            $os_path = import_py_mod("os.path");
            echo($os_path->join("a", "b"));
        ''')
        assert php_space.str_w(output[0]) == "a/b"

    def test_import_py_nested2_mod_func(self, php_space):
        output = self.run('''
            $os = import_py_mod("os");
            echo($os->path->join("a", "b"));
        ''')
        assert php_space.str_w(output[0]) == "a/b"

    def test_compile_py_mod(self, php_space):
        output = self.run('''
            $m = compile_py_mod("mymod", "def f(): print('hello')");
            echo($m->f());
        ''')
        assert output[0] == self.space.w_Null # XXX for now

    def test_call_func_int_args(self, php_space):
        output = self.run('''
            $m = compile_py_mod("mymod", "def f(x): return x+1");
            echo($m->f(665));
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_multiple_modules(self, php_space):
        output = self.run('''
            $m1 = compile_py_mod("mod1", "def f(x): return x+1");
            $m2 = compile_py_mod("mod2", "def g(x): return x-1");
            echo($m1->f(665));
            echo($m2->g(665));
        ''')
        assert php_space.int_w(output[0]) == 666
        assert php_space.int_w(output[1]) == 664

    def test_modules_intercall(self, php_space):
        output = self.run('''
            $m1 = compile_py_mod("mod1", "def f(x): return x+1");
            $m2 = compile_py_mod("mod2",
                "import mod1\ndef g(x): return mod1.f(x)");
            echo($m2->g(1336));
        ''')
        assert php_space.int_w(output[0]) == 1337

    def test_modules_intercall2(self, php_space):
        output = self.run('''
            $m1 = compile_py_mod("mod1", "def f(x): return x+1");
            $m2 = compile_py_mod("mod2",
                "import mod1\ndef g(x): return mod1.f(x)");
            $m3 = compile_py_mod("mod3",
                "import mod2\ndef h(x): return mod2.g(x)");
            echo($m3->h(41));
        ''')
        assert php_space.int_w(output[0]) == 42

    def test_fib(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def fib(n):
                if n == 0: return 0
                if n == 1: return 1
                return fib(n-1) + fib(n-2)
            EOD;

            $m = compile_py_mod("fib", $src);
            $expects = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144];

            for ($i = 0; $i < count($expects); $i++) {
                assert($m->fib($i) == $expects[$i]);
            }
        ''')

    def test_multitype_args(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cat(s, b, i):
                return "%s-%s-%s" % (s, b, i)
            EOD;

            $m = compile_py_mod("meow", $src);
            echo($m->cat("123", True, 666));
        ''')
        assert php_space.str_w(output[0]) == "123-True-666"

    def test_variadic_args_mod(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cat(*args):
                return "-".join([str(x) for x in args])
            EOD;

            $m = compile_py_mod("meow", $src);
            echo($m->cat(5, 4, 3, 2, 1, "Thunderbirds", "Are", "Go"));
        ''')
        assert php_space.str_w(output[0]) == "5-4-3-2-1-Thunderbirds-Are-Go"

    def test_variadic_args_func_global(self, php_space):
        output = self.run('''
            $src = "def f(*args): return len(args)";
            compile_py_func_global($src);

            echo f(1, 2, 3);
            echo f(4, 1);
            echo f(1, 1, 1, 2, 3);
        ''')
        assert php_space.int_w(output[0]) == 3
        assert php_space.int_w(output[1]) == 2
        assert php_space.int_w(output[2]) == 5

    def test_kwargs_exhaustive(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cat(x="111", y="222", z="333"):
                return "-".join([x, y, z])
            EOD;

            $m = compile_py_mod("meow", $src);
            echo($m->cat("abc", "def", "ghi"));
        ''')
        assert php_space.str_w(output[0]) == "abc-def-ghi"

    def test_kwargs_nonexhaustive(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cat(x="111", y="222", z="333"):
                return "-".join([x, y, z])
            EOD;

            $m = compile_py_mod("meow", $src);
            echo($m->cat("abc", "def"));
        ''')
        assert php_space.str_w(output[0]) == "abc-def-333"

    def test_kwargs_on_py_proxy(self, php_space):
        output = self.run('''
            $mod = import_py_mod("itertools");
            $src = <<<EOD
            def f(mod):
                it = mod.count(step=666) # should not explode
                vs = [ it.next() for i in range(3) ]
                return vs[-1]
            EOD;
            $f = compile_py_func($src);
            echo($f($mod));
        ''')
        assert php_space.int_w(output[0]) == 1332

    def test_kwargs_on_py_proxy2(self, php_space):
        output = self.run('''
            $mod = import_py_mod("itertools");
            $src = <<<EOD
            def f():
                it = mod.count(step=666) # should not explode
                vs = [ it.next() for i in range(3) ]
                return vs[-1]
            EOD;
            $f = compile_py_func($src);
            echo($f());
        ''')
        assert php_space.int_w(output[0]) == 1332

    def test_kwargs_on_py_proxy3(self, php_space):
        output = self.run('''
            $f = compile_py_func("def f(a, b=0, c=0): return a + b + c");
            $g = compile_py_func("def g(): return f(1, c=3)");
            echo($g());
        ''')
        assert php_space.int_w(output[0]) == 4

    def test_kwargs_on_py_proxy4(self, php_space):
        output = self.run('''
            $mk_src = <<<EOD
            def mk():
                code = 'def f(a, b=0, c=0): return a + b + c'
                import imp
                flibble = imp.new_module('flibble')
                exec code in flibble.__dict__
                return flibble
            EOD;
            $mk = compile_py_func($mk_src);
            $mod = $mk();

            $g = compile_py_func("def g(): return mod.f(1, c=3)");
            echo($g());
        ''')
        assert php_space.int_w(output[0]) == 4

    def test_phbridgeproxy_equality1(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cmp(x, y):
                return x == y
            EOD;
            $cmp = compile_py_func($src);

            class C { }
            $x = new C();
            echo($cmp($x, $x));
        ''')
        assert php_space.is_true(output[0])

    def test_phbridgeproxy_equality2(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cmp(x, y):
                return x == y
            EOD;
            $cmp = compile_py_func($src);

            class C { }
            $x = new C();
            $y = new C();
            echo($cmp($x, $y));
        ''')
        assert php_space.is_true(output[0])

    def test_phbridgeproxy_nequality1(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cmp(x, y):
                return x == y
            EOD;
            $cmp = compile_py_func($src);

            class C {
                public $val;
                function __construct($val) {
                    $this->val = $val;
                }
            }
            $x = new C(1);
            $y = new C(2);
            echo($cmp($x, $y));
        ''')
        assert not php_space.is_true(output[0])

    def test_phbridgeproxy_nequality2(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cmp(x, y):
                return x == y
            EOD;
            $cmp = compile_py_func($src);

            class C {
                public $val;
                function __construct($val) {
                    $this->val = $val;
                }
            }
            $x = new C(1);
            $y = new C(1);
            echo($cmp($x, $y));
        ''')
        assert php_space.is_true(output[0])

    def test_phbridgeproxy_instanceof(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def iof(a):
                return isinstance(a, C)
            EOD;

            $iof = compile_py_func($src);

            class C {}
            class D {}
            $x = new C;
            $y = new D;
            echo($iof($x));
            echo($iof($y));
        ''')
        assert php_space.is_true(output[0])
        assert not php_space.is_true(output[1])

    def test_phbridgeproxy_id1(self, php_space):
        output = self.run('''
            $src = <<<EOD
            @php_decor(refs=[0, 1])
            def is_chk(x, y):
                return str(id(x) == id(y))
            EOD;
            $is_chk = compile_py_func($src);

            class C {}
            $x = new C;
            $y = new c;
            echo($is_chk($x, $y) . " " . $is_chk($x, $x));
        ''')
        assert php_space.str_w(output[0]) == "False True"

    def test_phbridgeproxy_id2(self, php_space):
        output = self.run('''
            function f() {}
            function g() {}

            $src = <<<EOD
            def is_chk():
                return "%s %s" % (str(id(f) == id(g)), str(id(f) == id(f)))
            EOD;
            $is_chk = compile_py_func($src);

            echo($is_chk());
        ''')
        assert php_space.str_w(output[0]) == "False True"

    def test_phbridgeproxy_id3(self, php_space):
        output = self.run('''
            $src = <<<EOD
            @php_decor(refs=[0, 1])
            def is_chk(x, y):
                return str(id(x) == id(y))
            EOD;
            $is_chk = compile_py_func($src);

            class C {}
            $x = new C;
            $y = new c;
            echo($is_chk($x, $y) . " " . $is_chk($x, $x));
        ''')
        assert php_space.str_w(output[0]) == "False True"


    def test_phbridgeproxy_is1(self, php_space):
        output = self.run('''
            $src = <<<EOD
            @php_decor(refs=[0, 1])
            def is_chk(x, y):
                return str(x is y)
            EOD;
            $is_chk = compile_py_func($src);

            class C {}
            $x = new C;
            $y = new c;
            echo($is_chk($x, $y) . " " . $is_chk($x, $x));
        ''')
        assert php_space.str_w(output[0]) == "False True"

    def test_phbridgeproxy_is2(self, php_space):
        output = self.run('''
            function f() {}
            function g() {}

            $src = <<<EOD
            def is_chk():
                return "%s %s" % (str(f is g), str(f is f))
            EOD;
            $is_chk = compile_py_func($src);

            echo($is_chk());
        ''')
        assert php_space.str_w(output[0]) == "False True"

    def test_phbridgeproxy_is3(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def is_chk(x, y):
                return str(x is y)
            EOD;
            $is_chk = compile_py_func($src);

            class C {}
            $x = new C;
            $y = new c;
            echo($is_chk($x, $y) . " " . $is_chk($x, $x));
        ''')
        assert php_space.str_w(output[0]) == "False True"

    def test_callback_to_php(self, php_space):
        output = self.run('''
            function hello() {
                echo "foobar";
            }

            $src = <<<EOD
            def call_php():
                hello()
            EOD;

            $call_php = compile_py_func($src);
            $call_php();
        ''')
        assert php_space.str_w(output[0]) == "foobar"

    # XXX Test kwargs

    def test_obj_proxy(self, php_space):
        output = self.run('''
            $src = <<<EOD
            import sys
            def get():
                return sys
            EOD;
            $m = compile_py_mod("m", $src);
            echo($m->get()->__name__);
        ''')
        assert php_space.str_w(output[0]) == "sys"

    def test_compile_py_func(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def test():
                return "jibble"
            EOD;
            $test = compile_py_func($src);
            echo($test());
        ''')
        assert php_space.str_w(output[0]) == "jibble"

    def test_compile_py_func_accepts_only_a_func(self, php_space):
        output = self.run('''
            $src = <<<EOD
            import os # <--- nope
            def test():
                return "jibble"
            EOD;

            try {
                $test = compile_py_func($src);
                echo "test failed";
            } catch(BridgeException $e) {
                echo $e->getMessage();
            }
        ''')
        err_s = "compile_py_func: Python source must define exactly one function"
        assert php_space.str_w(output[0]) == err_s

    def test_compile_py_func_accepts_only_a_func2(self, php_space):
        output = self.run('''
            $src = "import os"; // not a func
            try {
                $test = compile_py_func($src);
            } catch(BridgeException $e) {
                echo $e->getMessage();
            }
        ''')
        err_s = "compile_py_func: Python source must define exactly one function"
        assert php_space.str_w(output[0]) == err_s

    def test_compile_py_func_args(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cat(x, y, z):
                return "%s-%s-%s" % (x, y, z)
            EOD;
            $cat = compile_py_func($src);
            echo($cat("t", "minus", 10));
        ''')
        assert php_space.str_w(output[0]) == "t-minus-10"

    def test_return_function_to_php(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def cwd():
                import os
                return os.getpid
            EOD;

            $cwd = compile_py_func($src);
            $x = $cwd();
            echo $x();
        ''')
        import os
        assert php_space.int_w(output[0]) == os.getpid()

    def test_compile_php_func(self, php_space):
        output = self.run('''
            $pysrc = <<<EOD
            def f():
                php_src = "function g(\$a, \$b) { return \$a + \$b; }"
                g = compile_php_func(php_src)
                return g(5, 4)
            EOD;

            $f = compile_py_func($pysrc);
            echo $f();
        ''')
        assert php_space.int_w(output[0]) == 9

    def test_compile_py_func(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def f(a, b):
                return sum([a, b])
            EOD;

            $f = compile_py_func($src);
            echo $f(4, 7);
        ''')
        assert php_space.int_w(output[0]) == 11

    def test_compile_py_func_global(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def test():
                return "jibble"
            EOD;
            compile_py_func_global($src);
            echo(test());
        ''')
        assert php_space.str_w(output[0]) == "jibble"

    def test_compile_py_func_global_returns_nothing(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def test(): pass
            EOD;
            $r = compile_py_func_global($src);
            echo($r);
        ''')
        assert php_space.w_Null == output[0]

    def test_compile_py_meth(self, php_space):
        output = self.run('''
            class C {};

            $src = <<<EOD
            def myMeth(self):
                return 10
            EOD;
            compile_py_meth("C", $src);
            $c = new C();
            echo($c->myMeth());
        ''')
        assert php_space.int_w(output[0]) == 10

    def test_compile_py_meth_static(self, php_space):
        output = self.run('''
            {
            class C {};

            $src = <<<EOD
            @php_decor(static=True)
            def myMeth():
                return 10
            EOD;
            compile_py_meth("C", $src);
            echo(C::myMeth());
            }
        ''')
        assert php_space.int_w(output[0]) == 10

    def test_compile_py_meth_static2(self, php_space):
        output = self.run('''
            {
            class C {};

            $src = <<<EOD
            @php_decor(static=True)
            def myMeth(a):
                return a
            EOD;
            compile_py_meth("C", $src);
            echo(C::myMeth(10));
            }
        ''')
        assert php_space.int_w(output[0]) == 10

    def test_compile_py_meth_private(self, php_space):
        output = self.run('''
            {
            class A {};

            $src = <<<EOD
            @php_decor(access="private")
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);
            $a = new A();
            $a->get();
            }
            ''',["Fatal error: Call to private method A::get() from context ''"])

    def test_compile_py_meth_private2(self, php_space):
        output = self.run('''
            {
            class A {};
            class B {
                function get($a) {
                    return $a->get();
                }
            };

            $src = <<<EOD
            @php_decor(access="private")
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);
            $a = new A();
            $b = new B();
            $b->get($a);
            }
            ''',["Fatal error: Call to private method A::get() from context 'B'"])

    def test_compile_py_meth_private_static(self, php_space):
        output = self.run('''
            {
            class A {};

            $src = <<<EOD
            @php_decor(access="private", static=True)
            def get():
                return 666
            EOD;
            compile_py_meth("A", $src);
            A::get();
            }
            ''',["Fatal error: Call to private method A::get() from context ''"])

    def test_compile_py_meth_private_static2(self, php_space):
        output = self.run('''
            {
            class A {};
            class B {
                function get() {
                    return A::get();
                }
            };

            $src = <<<EOD
            @php_decor(access="private", static=True)
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);
            $a = new A();
            $b = new B();
            $b->get();
            }
            ''',["Fatal error: Call to private method A::get() from context 'B'"])

    def test_compile_py_meth_protected(self, php_space):
        output = self.run('''
            {
            class A {};

            $src = <<<EOD
            @php_decor(access="protected")
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);
            $a = new A();
            $a->get();
            }
            ''',["Fatal error: Call to protected method A::get() from context ''"])

    def test_compile_py_meth_protected2(self, php_space):
        output = self.run('''
            {
            class A {};
            class B {
                function get($a) {
                    return $a->get();
                }
            };

            $src = <<<EOD
            @php_decor(access="protected")
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);
            $a = new A();
            $b = new B();
            $b->get($a);
            }
            ''',["Fatal error: Call to protected method A::get() from context 'B'"])

    def test_compile_py_meth_protected_static(self, php_space):
        output = self.run('''
            {
            class A {};

            $src = <<<EOD
            @php_decor(access="protected", static=True)
            def get():
                return 666
            EOD;
            compile_py_meth("A", $src);
            A::get();
            }
            ''',["Fatal error: Call to protected method A::get() from context ''"])

    def test_compile_py_meth_protected_static2(self, php_space):
        output = self.run('''
            {
            class A {};
            class B {
                function get() {
                    return A::get();
                }
            };

            $src = <<<EOD
            @php_decor(access="protected", static=True)
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);
            $a = new A();
            $b = new B();
            $b->get();
            }
            ''',["Fatal error: Call to protected method A::get() from context 'B'"])

    def test_compile_py_meth_public_static(self, php_space):
        output = self.run('''
            {
            class A {};

            $src = <<<EOD
            @php_decor(access="public", static=True)
            def get():
                return 666
            EOD;
            compile_py_meth("A", $src);
            echo(A::get());
            }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_public_static2(self, php_space):
        output = self.run('''
            {
            class A {};
            class B {
                function get() {
                    return A::get();
                }
            };

            $src = <<<EOD
            @php_decor(access="public", static=True)
            def get():
                return 666
            EOD;
            compile_py_meth("A", $src);
            $b = new B();
            echo($b->get());
            }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_public(self, php_space):
        output = self.run('''
            {
            class A {};

            $src = <<<EOD
            @php_decor(access="public")
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);
            $a = new A();
            echo($a->get());
            }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_public2(self, php_space):
        output = self.run('''
            {
            class A {};
            class B {
                function get($a) {
                    return $a->get();
                }
            };

            $src = <<<EOD
            @php_decor(access="public")
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);
            $a = new A();
            $b = new B();
            echo($b->get($a));
            }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_private_meth_subclass_call(self, php_space):
        output = self.run('''
            {
            class A {};
            $src = <<<EOD
            @php_decor(access="private")
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);

            class B extends A {
                function get2() {
                    return $this->get();
                }
            };

            $b = new B();
            $b->get2();
            }
        ''', ["Fatal error: Call to private method A::get() from context 'B'"])

    def test_compile_py_meth_private_static_meth_subclass_call(self, php_space):
        output = self.run('''
            {
            class A {};
            $src = <<<EOD
            @php_decor(access="private", static=True)
            def get():
                return 666
            EOD;
            compile_py_meth("A", $src);

            class B extends A {
                function get2() {
                    return A::get();
                }
            };

            $b = new B();
            $b->get2();
            }
        ''', ["Fatal error: Call to private method A::get() from context 'B'"])

    def test_compile_py_meth_protected_static_meth_subclass_call(self, php_space):
        output = self.run('''
            {
            class A {};
            $src = <<<EOD
            @php_decor(access="protected", static=True)
            def get():
                return 666
            EOD;
            compile_py_meth("A", $src);

            class B extends A {
                function get2() {
                    return A::get();
                }
            };

            $b = new B();
            echo($b->get2());
            }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_protected_meth_subclass_call(self, php_space):
        output = self.run('''
            {
            class A {};
            $src = <<<EOD
            @php_decor(access="protected")
            def get(self):
                return 666
            EOD;
            compile_py_meth("A", $src);

            class B extends A {
                function get2() {
                    return $this->get();
                }
            };

            $b = new B();
            echo($b->get2());
            }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_subclass(self, php_space):
        output = self.run('''
            {
            class C {};

            $src = <<<EOD
            def myMeth(self):
                return 10
            EOD;
            compile_py_meth("C", $src);

            class D extends C {};

            $d = new D();
            echo($d->myMeth());
            }
        ''')
        assert php_space.int_w(output[0]) == 10

    def test_compile_py_meth_attr_access(self, php_space):
        output = self.run('''
            class A {
                function __construct() {
                    $this->v = 666;
                }
            };
            $a = new A();

            class B {
            };

            $src = <<<EOD
            def bMeth(self):
                # We should pick up global dollar a, not class A.
                # Hippy class/func names are canonicalised lower case.
                a.v = 777
                return a.v
            EOD;
            compile_py_meth("B", $src);

            $b = new B();
            echo $b->bMeth();
        ''')
        assert php_space.int_w(output[0]) == 777

    def test_compile_py_meth_attr_overide(self, php_space):
        output = self.run('''
            class A {
                function m() { return 666; }
            };
            $a = new A();

            class B extends A {};

            $src = "def m(self): return 667";
            compile_py_meth("B", $src);

            $b = new B();
            echo $b->m();
        ''')
        assert php_space.int_w(output[0]) == 667

    def test_compile_py_meth_ctor(self, php_space):
        output = self.run('''
            class A {
            };
            $a = new A();

            $src = "def __construct(self): self.x = 666";
            compile_py_meth("A", $src);

            $a = new A();
            echo $a->x;
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_attr_access_other_inst(self, php_space):
        output = self.run('''
        {
            class A {
                    public $x = 666;
            };

            class B { }

            $src = "def f(self, other): return other.x";
            compile_py_meth("B", $src);

            $a = new A();
            $b = new B();
            echo $b->f($a);
        }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_and_call_from_subclass(self, php_space):
        output = self.run('''
        {
            class A {
                    public $x = 666;
            }

            $src = "def __construct(self): self.y = 1";
            compile_py_meth("A", $src);

            class B extends A {
                function __construct() {
                    parent::__construct();
                }
            }

            $a = new A();
            $b = new B();
            echo $b->y;
        }
        ''')
        assert php_space.int_w(output[0]) == 1

    def test_compile_py_meth_and_call_from_subclass_2(self, php_space):
        output = self.run('''
        {
            class A {
                    public $x = 666;
            }

            $src = "def __construct(self): self.y = 1";
            compile_py_meth("A", $src);

            class B extends A {
            }
            $src = "def __construct(self): A.__construct(self)";
            compile_py_meth("B", $src);

            $a = new A();
            $b = new B();
            echo $b->y;
        }
        ''')
        assert php_space.int_w(output[0]) == 1

    def test_compile_py_meth_and_get_static_member(self, php_space):
        output = self.run('''
        {
            class A {
                    public static $x = 666;
            }

            $src = "def __construct(self): self.y = 1";
            compile_py_meth("A", $src);

            $src = "def getx(): return A.x";
            $getx = compile_py_func($src);
            echo $getx();

        }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_compile_py_meth_and_lookup_nonexistent_member(self, php_space):
        output = self.run('''
        {
        class A {
                public static $x = 666;
        }

        $src = "def __construct(self): self.y = 1";
        compile_py_meth("A", $src);

        $src = <<<EOD
        def getx():
            try:
                A.idontexist
                return "fail"
            except BridgeError as e:
                return e.message
        EOD;

        $getx = compile_py_func($src);
        echo $getx();

        }
        ''')
        assert php_space.str_w(output[0]) == "Wrapped PHP class has not attribute 'idontexist'"

    def test_subclass_call_php_method_using_this_from_python(self, php_space):
        output = self.run('''
        {
            class A {
                function foo(){
                    $this->a = 1;
                }
            }

            class B extends A {
            }
            $src = "def foo(self): A.foo(self)";
            compile_py_meth("B", $src);

            $b = new B();
            $b->foo();
            echo $b->a;
        }
        ''')
        assert php_space.str_w(output[0]) == "1"

    def test_get_static_property_from_python(self, php_space):
        output = self.run('''
        {
            class A {
                private static $MY_PROP = 666;
            };

            $src = "def test(self): return A.MY_PROP";
            compile_py_meth("A", $src);

            $a = new A();
            echo $a->test();
        }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_set_static_property_from_python(self, php_space):
        output = self.run('''
        {
            class A {
                public static $MY_PROP = 111;
            };

            $src = "def test(self): A.MY_PROP = 666;";
            compile_py_meth("A", $src);

            $a = new A();
            $a->test();
            echo A::$MY_PROP;
        }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_get_class_const(self, php_space):
        output = self.run('''
        {
            class A {
                const J = 10;
            };

            $src = "def f(): return A.J";
            $f = compile_py_func($src);

            echo $f();
        }
        ''')
        assert php_space.int_w(output[0]) == 10

    @pytest.mark.xfail
    def test_java_sytle_ctor_name_embedding(self, php_space):
        output = self.run('''
        {
            class A {
                public $j = 0;
            };

            # method same name as class is a constructor
            $src = "def A(self): self.j = 666";
            compile_py_meth("A", $src);

            $a = new A();
            echo $a->j;
        }
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_pycode_cache(self, php_space):
        output = self.run('''
            // compile same function twice
            $src = "def f(): pass";
            $f = compile_py_func($src);
            $ff = compile_py_func($src);

            compile_py_func_global("def check(f1, f2): return f1.__code__ is f2.__code__");
            echo check($f, $ff);
        ''')
        assert php_space.is_true(output[0])

    def test_kwarg_from_php(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def f(a="a", b="b", c="c"):
                  return a + b + c
            EOD;

            $f = compile_py_func_global($src);

            echo call_py_func("f", [], ["a" => "z"]);
            echo call_py_func("f", ["z"], ["c" => "o"]);
            echo call_py_func("f", [], ["a" => "x", "b" => "y", "c" => "z"]);
            echo call_py_func("f", [], ["b" => "y", "c" => "z", "a" => "x"]);
            echo call_py_func("f", ["o", "p"], ["c" => "z"]);
            echo call_py_func("f", [], []);
            echo call_py_func("f", ["j", "k", "l"], []);
        ''')
        assert php_space.str_w(output[0]) == "zbc"
        assert php_space.str_w(output[1]) == "zbo"
        assert php_space.str_w(output[2]) == "xyz"
        assert php_space.str_w(output[3]) == "xyz"
        assert php_space.str_w(output[4]) == "opz"
        assert php_space.str_w(output[5]) == "abc"
        assert php_space.str_w(output[6]) == "jkl"

    def test_kwarg_from_php2(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def f(a="a", b="b", c="c"):
                  return a + b + c
            EOD;

            $f = compile_py_func($src);

            echo call_py_func($f, [], ["a" => "z"]);
            echo call_py_func($f, ["z"], ["c" => "o"]);
            echo call_py_func($f, [], ["a" => "x", "b" => "y", "c" => "z"]);
            echo call_py_func($f, [], ["b" => "y", "c" => "z", "a" => "x"]);
            echo call_py_func($f, ["o", "p"], ["c" => "z"]);
            echo call_py_func($f, [], []);
            echo call_py_func($f, ["j", "k", "l"], []);
        ''')
        assert php_space.str_w(output[0]) == "zbc"
        assert php_space.str_w(output[1]) == "zbo"
        assert php_space.str_w(output[2]) == "xyz"
        assert php_space.str_w(output[3]) == "xyz"
        assert php_space.str_w(output[4]) == "opz"
        assert php_space.str_w(output[5]) == "abc"
        assert php_space.str_w(output[6]) == "jkl"

    def test_kwarg_from_php3(self, php_space):
        output = self.run('''
            class A {};
            $src = <<<EOD
            @php_decor(static=True)
            def f(a="a", b="b", c="c"):
                  return a + b + c
            EOD;

            compile_py_meth("A", $src);

            echo call_py_func("A::f", [], ["a" => "z"]);
            echo call_py_func("A::f", ["z"], ["c" => "o"]);
            echo call_py_func("A::f", [], ["a" => "x", "b" => "y", "c" => "z"]);
            echo call_py_func("A::f", [], ["b" => "y", "c" => "z", "a" => "x"]);
            echo call_py_func("A::f", ["o", "p"], ["c" => "z"]);
            echo call_py_func("A::f", [], []);
            echo call_py_func("A::f", ["j", "k", "l"], []);
        ''')
        assert php_space.str_w(output[0]) == "zbc"
        assert php_space.str_w(output[1]) == "zbo"
        assert php_space.str_w(output[2]) == "xyz"
        assert php_space.str_w(output[3]) == "xyz"
        assert php_space.str_w(output[4]) == "opz"
        assert php_space.str_w(output[5]) == "abc"
        assert php_space.str_w(output[6]) == "jkl"

    def test_kwarg_from_php4(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def f():
                class A(object):
                    @staticmethod
                    def f(a="a", b="b", c="c"):
                        return a + b + c

                phpsrc = "function g() { return call_py_func('A::f', [], ['a' => 'z']); }";
                g = compile_php_func(phpsrc)
                return g()
            EOD;

            compile_py_func_global($src);

            echo f();
        ''')
        assert php_space.str_w(output[0]) == "zbc"

    def test_kwarg_from_php5(self, php_space):
        output = self.run('''
            class A {};
            $src = <<<EOD
            def f(self, a="a", b="b", c="c"):
                  return a + b + c
            EOD;
            compile_py_meth("A", $src);

            $a = new A();

            echo call_py_func([$a, "f"], [], ["a" => "z"]);
            echo call_py_func([$a, "f"], ["z"], ["c" => "o"]);
            echo call_py_func([$a, "f"], [], ["a" => "x", "b" => "y", "c" => "z"]);
            echo call_py_func([$a, "f"], [], ["b" => "y", "c" => "z", "a" => "x"]);
            echo call_py_func([$a, "f"], ["o", "p"], ["c" => "z"]);
            echo call_py_func([$a, "f"], [], []);
            echo call_py_func([$a, "f"], ["j", "k", "l"], []);
        ''')
        assert php_space.str_w(output[0]) == "zbc"
        assert php_space.str_w(output[1]) == "zbo"
        assert php_space.str_w(output[2]) == "xyz"
        assert php_space.str_w(output[3]) == "xyz"
        assert php_space.str_w(output[4]) == "opz"
        assert php_space.str_w(output[5]) == "abc"
        assert php_space.str_w(output[6]) == "jkl"

    def test_kwarg_from_php6(self, php_space):
        output = self.run('''
            class A {};
            $src = <<<EOD
            @php_decor(static=True)
            def f(a="a", b="b", c="c"):
                  return a + b + c
            EOD;
            compile_py_meth("A", $src);

            echo call_py_func(["A", "f"], [], ["a" => "z"]);
            echo call_py_func(["A", "f"], ["z"], ["c" => "o"]);
            echo call_py_func(["A", "f"], [], ["a" => "x", "b" => "y", "c" => "z"]);
            echo call_py_func(["A", "f"], [], ["b" => "y", "c" => "z", "a" => "x"]);
            echo call_py_func(["A", "f"], ["o", "p"], ["c" => "z"]);
            echo call_py_func(["A", "f"], [], []);
            echo call_py_func(["A", "f"], ["j", "k", "l"], []);
        ''')
        assert php_space.str_w(output[0]) == "zbc"
        assert php_space.str_w(output[1]) == "zbo"
        assert php_space.str_w(output[2]) == "xyz"
        assert php_space.str_w(output[3]) == "xyz"
        assert php_space.str_w(output[4]) == "opz"
        assert php_space.str_w(output[5]) == "abc"
        assert php_space.str_w(output[6]) == "jkl"

    def test_kwarg_from_php7(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def mk():
                class F(object):
                    def __call__(self, a="a", b="b", c="c"):
                          return a + b + c
                return F()
            EOD;
            compile_py_func_global($src);

            $f = mk();

            echo call_py_func($f, [], ["a" => "z"]);
            echo call_py_func($f, ["z"], ["c" => "o"]);
            echo call_py_func($f, [], ["a" => "x", "b" => "y", "c" => "z"]);
            echo call_py_func($f, [], ["b" => "y", "c" => "z", "a" => "x"]);
            echo call_py_func($f, ["o", "p"], ["c" => "z"]);
            echo call_py_func($f, [], []);
            echo call_py_func($f, ["j", "k", "l"], []);
        ''')
        assert php_space.str_w(output[0]) == "zbc"
        assert php_space.str_w(output[1]) == "zbo"
        assert php_space.str_w(output[2]) == "xyz"
        assert php_space.str_w(output[3]) == "xyz"
        assert php_space.str_w(output[4]) == "opz"
        assert php_space.str_w(output[5]) == "abc"
        assert php_space.str_w(output[6]) == "jkl"

    def test_kwarg_from_php8(self, php_space):
        output = self.run('''
            class A { static function k() { return "fail"; } };
            $pysrc = <<<EOD
            def f():
                class A(object):
                    @staticmethod
                    def k():
                        return "OK"
                php_src = "function g() { return call_py_func('A::k', [], []); }"
                g = compile_php_func(php_src)
                return g
            EOD;
            $f = compile_py_func($pysrc);
            $g = $f();

            echo $g();
        ''')
        assert php_space.str_w(output[0]) == "OK"

    def test_kwarg_from_php9(self, php_space):
        output = self.run('''
            $src = <<<EOD
            def mk():
                class F(object):
                    @staticmethod
                    def x(a="a", b="b", c="c"):
                          return a + b + c
                return F
            EOD;
            compile_py_func_global($src);

            $f = mk();

            echo call_py_func([$f, "x"], [], ["a" => "z"]);
            echo call_py_func([$f, "x"], ["z"], ["c" => "o"]);
            echo call_py_func([$f, "x"], [], ["a" => "x", "b" => "y", "c" => "z"]);
            echo call_py_func([$f, "x"], [], ["b" => "y", "c" => "z", "a" => "x"]);
            echo call_py_func([$f, "x"], ["o", "p"], ["c" => "z"]);
            echo call_py_func([$f, "x"], [], []);
            echo call_py_func([$f, "x"], ["j", "k", "l"], []);
        ''')
        assert php_space.str_w(output[0]) == "zbc"
        assert php_space.str_w(output[1]) == "zbo"
        assert php_space.str_w(output[2]) == "xyz"
        assert php_space.str_w(output[3]) == "xyz"
        assert php_space.str_w(output[4]) == "opz"
        assert php_space.str_w(output[5]) == "abc"
        assert php_space.str_w(output[6]) == "jkl"

    def test_new_on_py_class(self, php_space):
        output = self.run('''
            $mod = import_py_mod("__builtin__");
            $s1 = new $mod->set();
            $s1->copy();
        ''')

    @pytest.mark.xfail
    def test_pass_php_array_to_py_func(self, php_space):
        output = self.run('''
            $mod = import_py_mod("__builtin__");
            $s1 = new $mod->set([345]);
            echo $s1->pop();
        ''')
        # we get 0 because the PHP array becomes a python dict-like
        # and the Python set constructor does not call as_list().
        assert php_space.int_w(output[0]) == 345

    def test_randrange_from_py(self, php_space):
        self.engine.py_space.initialize()
        output = self.run('''
        $random = import_py_mod("random");
        $num = $random->randrange(10, 20);
        echo $num;
        ''')
        from hippy.objects.intobject import W_IntObject
        assert isinstance(output[0], W_IntObject)

    def test_unbound_php_meth_adapter(self, php_space):
        output = self.run('''
        {
            class Base {
                public $a = 0;
                function __construct($a) {
                    $this->a = $a;
                }
            }

            class Sub extends Base {
            }

            $src = "def __construct(self, a): Base.__construct(self, a)";
            compile_py_meth("Sub", $src);

            $inst = new Sub(6);
            echo $inst->a;
        }
        ''')
        assert php_space.int_w(output[0]) == 6

    def test_call_php_static_meth_from_python_meth(self, php_space):
        output = self.run('''
            class A {
                static function add($a, $b) {
                    return $a + $b;
                }
            }
            $src = <<<EOD
            @php_decor(static=True)
            def addpy(a, b):
                return A.add(a, b)
            EOD;
            compile_py_meth("A", $src);

            echo A::addpy(4, 5);
        ''')
        assert php_space.int_w(output[0]) == 9

    def test_call_php_dynamic_meth_from_python_meth(self, php_space):
        output = self.run('''
            class A {
                function add($a, $b) {
                    return $a + $b;
                }
            }
            $src = <<<EOD
            def addpy(self, a, b):
                return self.add(a, b)
            EOD;
            compile_py_meth("A", $src);

            $a = new A();
            echo $a->addpy(4, 5);
        ''')
        assert php_space.int_w(output[0]) == 9

    def test_py_meth_call_py_static_meth(self, php_space):
        output = self.run('''
        class A {};

        $src = "def f(self): return A.g()";
        compile_py_meth("A", $src);

        $src2 = <<<EOD
        @php_decor(static=True)
        def g():
            return 456
        EOD;
        compile_py_meth("A", $src2);

        $a = new A();
        echo $a->f();
        ''')
        assert php_space.int_w(output[0]) == 456

    def test_call_pyclass_static_meth(self, php_space):
        output = self.run('''
        $src = <<<EOD
        def f():
            class A:
                @staticmethod
                def x():
                    return 666
            return A
        EOD;
        compile_py_func_global($src);
        $a = f();
        echo($a::x());
        ''')
        assert php_space.int_w(output[0]) == 666

    def test_unwrap_pyclassadapter(self, php_space):
        output = self.run('''
        $src1 = <<<EOD
        def f():
            class A:
                x = 1212
            return A
        EOD;
        compile_py_func_global($src1);

        $src2 = <<<EOD
        def g(a):
            return a.x
        EOD;
        compile_py_func_global($src2);

        echo g(f());
        ''')
        assert php_space.int_w(output[0]) == 1212

    def test_call_private_method_from_same_class_in_py(self, php_space):
        output = self.run('''
        {
        class A {
            private function secret() { return 31415; }
        }

        $pysrc = <<<EOD
        def get_secret(self):
            return self.secret()
        EOD;
        compile_py_meth("A", $pysrc);

        $a = new A();
        echo $a->get_secret();
        }
        ''')
        assert php_space.int_w(output[0]) == 31415

    def test_call_protected_method_from_same_class_in_py(self, php_space):
        output = self.run('''
        {
        class A {
            protected function secret() { return 31415; }
        }

        $pysrc = <<<EOD
        def get_secret(self):
            return self.secret()
        EOD;
        compile_py_meth("A", $pysrc);

        $a = new A();
        echo $a->get_secret();
        }
        ''')
        assert php_space.int_w(output[0]) == 31415

    def test_call_protected_method_from_subclass_in_py(self, php_space):
        output = self.run('''
        {
        class A {
            protected function secret() { return 31415; }
        }

        class B extends A {}

        $pysrc = <<<EOD
        def get_secret(self):
            return self.secret()
        EOD;
        compile_py_meth("B", $pysrc);

        $b = new B();
        echo $b->get_secret();
        }
        ''')
        assert php_space.int_w(output[0]) == 31415

    def test_set_protected_attr_from_same_class_in_py(self, php_space):
        output = self.run('''
        {
        class A {
            protected $secret = 454;
        }

        $pysrc = <<<EOD
        def set_secret(self):
            self.secret = 555
            return self.secret
        EOD;
        compile_py_meth("A", $pysrc);

        $a = new A();
        echo $a->set_secret();
        }
        ''')
        assert php_space.int_w(output[0]) == 555

    def test_get_protected_attr_from_same_class_in_py(self, php_space):
        output = self.run('''
        {
        class A {
            protected $secret = 454;
        }

        $pysrc = <<<EOD
        def get_secret(self):
            return self.secret
        EOD;
        compile_py_meth("A", $pysrc);

        $a = new A();
        echo $a->get_secret();
        }
        ''')
        assert php_space.int_w(output[0]) == 454

    def test_set_protected_attr_from_subclass_in_py(self, php_space):
        output = self.run('''
        {
        class A {
            protected $secret = 454;
        }

        class B extends A{};

        $pysrc = <<<EOD
        def set_secret(self):
            self.secret = 555
            return self.secret
        EOD;
        compile_py_meth("B", $pysrc);

        $b = new B();
        echo $b->set_secret();
        }
        ''')
        assert php_space.int_w(output[0]) == 555

    def test_get_protected_attr_from_subclass_in_py(self, php_space):
        output = self.run('''
        {
        class A {
            protected $secret = 454;
        }

        class B extends A{};

        $pysrc = <<<EOD
        def get_secret(self):
            return self.secret
        EOD;
        compile_py_meth("B", $pysrc);

        $b = new B();
        echo $b->get_secret();
        }
        ''')
        assert php_space.int_w(output[0]) == 454

    # This is quite unintuitive
    # If you set a private attr which you don't have access to, you make a
    # new field of the same name in the superclass.
    def test_set_private_attr_from_subclass_in_py(self, php_space):
        output = self.run('''
        {
        class A {
            private $secret = 454;

            function get_secret_a() {
                return $this->secret;
            }
        }

        class B extends A{
            function get_secret_b() {
                return $this->secret;
            }
        };

        $pysrc = <<<EOD
        def set_secret(self):
            self.secret = 555
            return self.secret
        EOD;
        compile_py_meth("B", $pysrc);

        $b = new B();
        $b->set_secret(); // will not fail!
        echo $b->get_secret_a();
        echo $b->get_secret_b();
        }
        ''')
        assert php_space.int_w(output[0]) == 454
        assert php_space.int_w(output[1]) == 555


class TestPyPyBridgeInterp(object):

    def test_php_code_cache(self):
        from pypy.config.pypyoption import get_pypy_config
        from hippy.interpreter import Interpreter
        from pypy.config.pypyoption import enable_translationmodules
        from pypy.objspace.std import StdObjSpace as PyStdObjSpace
        from hippy.objspace import getspace
        from pypy.module.__builtin__.hippy_bridge import (
            _compile_php_func_from_string_cached)

        pypy_config = get_pypy_config(translating=False)
        py_space = PyStdObjSpace(pypy_config)
        php_space = getspace()
        interp = Interpreter(php_space, py_space=py_space)

        src = '<?php function f($a) { return "hello $a"; } ?>'

        # compile same source code twice
        comp1 = _compile_php_func_from_string_cached(interp, src)
        comp2 = _compile_php_func_from_string_cached(interp, src)

        # This function however, is an imposter
        src2 = '<?php function f($a) { return ""; } ?>'
        comp3 = _compile_php_func_from_string_cached(interp, src2)

        assert comp1 is comp2
        assert comp1 is not comp3
        assert comp2 is not comp3

    def test_php_code_cache_clone(self):
        from pypy.config.pypyoption import get_pypy_config
        from hippy.interpreter import Interpreter
        from pypy.config.pypyoption import enable_translationmodules
        from pypy.objspace.std import StdObjSpace as PyStdObjSpace
        from hippy.objspace import getspace
        from pypy.module.__builtin__.hippy_bridge import (
            _compile_php_func_from_string_cached)

        pypy_config = get_pypy_config(translating=False)
        py_space = PyStdObjSpace(pypy_config)
        php_space = getspace()
        interp = Interpreter(php_space, py_space=py_space)

        src = '<?php function f($a) { return "hello $a"; } ?>'

        # compile same source code twice
        bc1 = _compile_php_func_from_string_cached(interp, src)
        bc1.py_scope = 1 # would really be a Py_Scope instance.
        bc2 = bc1.clone()

        check_attrs = ["code", "name", "filename", "startlineno",
                       "sourcelines", "consts", "names", "varnames",
                       "stackdepth", "var_to_pos", "names_to_pos",
                       "late_declarations", "classes", "functions",
                       "method_of_class", "bc_mapping", "superglobals",
                       "this_var_num", "static_vars"]

        for name in check_attrs:
            a1 = getattr(bc1, name)
            a2 = getattr(bc2, name)
            assert a1 == a2

        assert bc1.py_scope is not bc2.py_scope
